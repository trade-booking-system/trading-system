from fastapi import HTTPException
from schema import Trade, History
from utils.tickers import ValidTickers
from typing import IO, Union
from csv import DictReader
from pydantic import ValidationError
from io import StringIO


import redis

def booktrade(client: redis.Redis, trade: Trade, tickers: ValidTickers):
    if not tickers.is_valid_ticker(trade.stock_ticker.upper()):
        raise HTTPException(status_code= 404, detail= "invalid stock ticker")
    key = f"trades:{trade.account}:{trade.date.isoformat()}"
    history= History()
    history.trades.append(trade)
    json_data= history.json()
    client.hset(key, trade.id, json_data)
    client.publish("updatePositions", f"{trade.account}:{trade.stock_ticker}:{get_amount(trade)}:{trade.price}")
    client.publish("tradeUpdates", f"create: {trade.json()}")
    return {"Key": key, "Field": trade.id}

def booktrades_bulk(client: redis.Redis, trades: list[Trade]):
    for trade in trades:
        booktrade(client, trade)
    return {"message": "Trades with Bulk worked!"}

def update_trade(trade_id, account, date, updated_type, updated_amount, updated_price, client: redis.Redis):
    key= f"trades:{account}:{date}"
    json_history= client.hget(key, trade_id)
    if json_history == None:
        raise HTTPException(status_code= 404, detail= "trade does not exist")
    history= History.parse_raw(json_history)
    old_trade= history.get_current_trade()
    trade= create_updated_trade(updated_amount, updated_type, updated_price, old_trade)
    history.add_updated_trade(trade)
    # undo previous version of trade and add new trade
    client.publish("updatePositions", f"{trade.account}:{trade.stock_ticker}:{get_amount(old_trade)}:{-old_trade.price}")
    client.publish("updatePositions", f"{trade.account}:{trade.stock_ticker}:{get_amount(trade)}:{trade.price}")
    client.publish("tradeUpdates", f"update: {trade.json()}")
    client.hset(key, trade_id, history.json())
    return {"Key": key, "Field": trade.id, "Version": trade.version}

def create_updated_trade(updated_amount, updated_type, updated_price, old_trade: Trade) -> Trade:
        if updated_amount == None:
            updated_amount= old_trade.amount
        if updated_type == None:
            updated_type= old_trade.type
        if updated_price == None:
            updated_price= old_trade.price
        version= old_trade.version+1
        return Trade(id= old_trade.id, account= old_trade.account, stock_ticker= old_trade.stock_ticker, user= old_trade.user,
                      version= version, type= updated_type, amount= updated_amount, price= updated_price)

def get_trades(client: redis.Redis):
    trades= []
    for key in client.scan_iter("trades:*"):
        for _, json_object in client.hscan_iter(key):
            trade_object= History.parse_raw(json_object).get_current_trade()
            trades.append(trade_object)
    return trades

def query_trades(account: str, year: str, month: str, day: str, client: redis.Redis):
    trades = []
    for key in client.scan_iter(f"trades:{account}:{year}-{month}-{day}"):
        for _, json_object in client.hscan_iter(key):
            trade_object= History.parse_raw(json_object).get_current_trade()
            trades.append(trade_object)
    return trades

def get_trade_history(trade_id, account, date, client: redis.Redis):
    key= f"trades:{account}:{date}"
    json_history= client.hget(key, trade_id)
    if json_history == None:
        raise HTTPException(status_code= 404, detail= "trade does not exist")
    return History.parse_raw(json_history)

def get_accounts(client: redis.Redis):
    keys = client.scan_iter("trades:*")
    accounts = set()
    for key in keys:
        accounts.add(key.split(":")[1])
    return accounts

def get_amount(trade: Trade):
    return trade.amount if trade.type == "buy" else -trade.amount

def csv_to_json(data: bytes):
    text: str = data.decode()
    reader = DictReader(StringIO(text))

    trades = []
    for row in reader:
        try:
            trade = create_trade_from_row(row)
            trades.append(trade_to_dict(trade))
        except ValidationError as e:
            raise HTTPException(status_code=400, detail="Invalid trade data in CSV file.")

    return trades


# Existing function
def create_trade_from_row(row):
    return Trade(
        account=row["accounts"],
        type=row["buyOrSell"],
        stock_ticker=row["tickers"],
        amount=int(row["shares"]),
        user=row.get("user", "101010"),
        price=float(row["price"]) if row["price"] else None
    )

# Existing function
def trade_to_dict(trade: Trade):
    return {
        "tickers": trade.stock_ticker,
        "accounts": trade.account,
        "buyOrSell": trade.type,
        "shares": str(trade.amount),
        "price": str(trade.price)
    }
