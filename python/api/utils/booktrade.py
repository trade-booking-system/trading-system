from fastapi import HTTPException
from schema import Trade, History
import redis

def booktrade(client: redis.Redis, trade: Trade):
    key = f"trades:{trade.account}:{trade.date.isoformat()}"
    history= History()
    history.trades.append(trade)
    json_data= history.json()
    client.hset(key, trade.id, json_data)
    client.publish("updatePositions", f"{trade.account}:{trade.stock_ticker}:{get_amount(trade)}")
    return {"Key": key, "Field": trade.id}

def update_trade(trade_id, account, date, updated_type, updated_amount, client: redis.Redis):
    key= f"trades:{account}:{date}"
    json_history= client.hget(key, trade_id)
    if json_history == None:
        raise HTTPException(status_code= 404, detail= "trade does not exist")
    history= History.parse_raw(json_history)
    old_trade= history.get_current_trade()
    trade= history.update_trade(updated_type, updated_amount, old_trade)
    # undo previous version of trade and add new trade
    amount= get_amount(trade) - get_amount(old_trade)
    client.publish("updatePositions", f"{trade.account}:{trade.stock_ticker}:{amount}")
    client.hset(key, trade_id, history.json())
    return {"Key": key, "Field": trade.id, "Version": trade.version}

def get_trades(client: redis.Redis):
    trades= []
    for key in client.keys("trades:*"):
        data= client.hgetall(key)
        for json_object in data.values():
            trade_object= History.parse_raw(json_object).get_current_trade()
            trades.append(trade_object)
    return trades

def query_trades(account: str, year: str, month: str, day: str, client: redis.Redis):
    trades = []
    for key in client.keys(f"trades:{account}:{year}-{month}-{day}"):
        data = client.hgetall(key)
        for json_object in data.values():
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
    keys = client.keys("trades:*")
    accounts = set()
    for key in keys:
        accounts.add(key.split(":")[1])
    return accounts

def get_amount(trade: Trade):
    return trade.amount if trade.type == "buy" else -trade.amount
