from apscheduler.schedulers.background import BackgroundScheduler
from strategies.orb import ORB

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Example of scheduling the ORB strategy to run every minute
    # In a real app, this would be configured by the user
    orb_parameters = {
        "candle_time_frame": 5,
        "start_time": "09:15",
        "end_time": "15:30",
        "quantity": 1,
        "stop_loss": 10,
        "target_profit": 20,
        "trailing_stop_loss": 5,
    }
    orb_strategy = ORB(orb_parameters)
    scheduler.add_job(orb_strategy.execute, 'interval', minutes=1)
    scheduler.start()
