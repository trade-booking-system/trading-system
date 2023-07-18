from redis import Redis
from datetime import datetime, timedelta, date
from schema import Position, Trade, History
from utils.booktrade import get_trades, get_amount
from listener import listener_base

class PositionListener(listener_base):
    def __init__(self):
        self.cache: dict[str, dict[str, int]] = {}
        super().__init__()

    def get_handlers(self):
        return {
            "tradesInfo": self.trade_updates_handler
        }
    
    def startup(self):
        self.recover()

    def trade_updates_handler(self, msg):
        data: str= msg["data"]
        account, stock_ticker, amount= data.split(":")
        self.queue.put_nowait((self.update_position_and_notify, (account, stock_ticker, int(amount))))

    def update_position_and_notify(self, account: str, stock_ticker: str, amount_added: int):
        self.update_position(account, stock_ticker, amount_added)
        self.client.publish("positionUpdates", f"{account}:{stock_ticker}")

    def update_position(self, account: str, stock_ticker: str, amount_added: int):
        key = "positions:"+account
        stock_tickers= self.cache.get(account, dict())
        self.cache[account]= stock_tickers
        old_amount= stock_tickers.get(stock_ticker)
        if old_amount == None:
            position_json= self.client.hget(key, stock_ticker)
            if position_json != None:
                old_position= Position.parse_raw(position_json)
                old_amount= old_position.amount
            else:
                old_amount= 0
        amount= old_amount + amount_added

        stock_tickers[stock_ticker]= amount
        position= Position(account= account, stock_ticker= stock_ticker, amount= amount, 
                        last_aggregation_time= datetime.now(), last_aggregation_host= "host")
        
        self.client.hset(key, stock_ticker, position.json())
        self.client.publish("positionUpdatesWS", f"position:{position.json()}")

    def recover(self):
        current_date= datetime.now().date()
        stocks: list[str]= self.client.smembers("p&lStocks")
        trades_cache: dict[str, list[Trade]]= dict()
        for stock in stocks:
            account, ticker= stock.split(":")
            last_aggregation_time= self.get_last_aggregation_time(self.client, account, ticker)
            date = last_aggregation_time.date()
            trades: list[Trade]= []
            while date <= current_date:
                trades.extend(self.get_trades(account, ticker, date, trades_cache))
                date= date + timedelta(1)

            for trade in trades:
                if trade.date != last_aggregation_time.date() or trade.time > last_aggregation_time.time():
                    self.update_position(trade.account, trade.stock_ticker, get_amount(trade))

    def get_trades(self, account: str, ticker: str, date: date, cache: dict[str, Trade]) -> list[Trade]:
        trades= list()
        days_trades= self.get_trades_by_day(account, date, cache)
        for trade in days_trades:
            if trade.stock_ticker == ticker:
                trades.append(trade)
        return trades

    def get_trades_by_day(self, account: str, date: date, cache: dict[str, list[Trade]]) -> list[Trade]:
        key= f"trades:{account}:{date.isoformat()}"
        trades= cache.get(key)
        if trades != None:
            return trades
        trades= []
        hashes= self.client.hgetall(key)
        if hashes != None:
            json_trades= hashes.values()
            for json_trade in json_trades:
                trades.append(History.parse_raw(json_trade).get_current_trade())
        cache[key]= trades
        return trades

    @staticmethod
    def get_last_aggregation_time(client: Redis, account, ticker) -> datetime:
        json_position= client.hget("positions:"+account, ticker)
        if json_position != None:
            return Position.parse_raw(json_position).last_aggregation_time
        keys: list[str]= client.keys(f"trades:{account}:*")
        date= keys[0].split(":")[2]
        return datetime.fromisoformat(date)

    def rebuild(self):
        keys= self.client.keys("positions:*")
        for key in keys:
            self.client.delete(key)
        self.cache= dict()
        trades: list[Trade]= get_trades(self.client)
        for trade in trades:
            self.update_position(trade.account, trade.stock_ticker, trade.amount)

PositionListener()