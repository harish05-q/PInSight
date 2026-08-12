import redis
from rq import Queue

from app.config import settings

# Setup Redis connection and Queue for background tasks
redis_conn = redis.from_url(settings.redis_url)
q = Queue(connection=redis_conn)
