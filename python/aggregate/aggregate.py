from redis import Redis
from datetime import datetime
from schema import Position
import signal
import os

def trade_handler(msg):
    data= msg["data"]
    account, stock_ticker, value= data.split(":")
    value= int(value)
    key = "positions:"+account
    json_old_position = client.hget(key, stock_ticker)
    old_value= 0
    if json_old_position != None:
        old_value= Position.parse_raw(json_old_position).amount
    position= Position(account= account, stock_ticker= stock_ticker, amount= old_value+value, 
                       last_aggregation_time= datetime.now(), last_aggregation_host= "host")
    client.hset(key, stock_ticker, position.json())

def termination_handler(signum, frame):
    thread.stop()
    thread.join()
    sub.close()
    client.close()

client = Redis(host = os.getenv("REDIS_HOST"), port = 6379, db = 1, decode_responses = True)
sub= client.pubsub(ignore_subscribe_messages= True)

sub.subscribe(**{"updatePositions":trade_handler})
thread= sub.run_in_thread()
signal.signal(signal.SIGTERM, termination_handler)
