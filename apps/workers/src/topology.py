from apps.workers.src.config import settings
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

broker = RabbitBroker(settings.rabbitmq_url)

pm_exchange = RabbitExchange("pm.events", type=ExchangeType.TOPIC, durable=True)
dlx_exchange = RabbitExchange("pm.dlx", type=ExchangeType.TOPIC, durable=True)

# Cola para recibir webhooks de Git
git_queue = RabbitQueue(
    "git.events",
    durable=True,
    routing_key="git.events.received",
    arguments={
        "x-dead-letter-exchange": "pm.dlx",
        "x-dead-letter-routing-key": "git.events.dead",
    },
)

# Cola de Time Logs normal con DLX
fin_queue = RabbitQueue(
    "fin.time_logged",
    durable=True,
    routing_key="fin.time_logged.recorded",
    arguments={
        "x-dead-letter-exchange": "pm.dlx",
        "x-dead-letter-routing-key": "fin.time_logged.dead",
    },
)

# Cola de Time Logs prioritaria VIP con DLX y prioridad
fin_vip_queue = RabbitQueue(
    "fin.time_logged.vip",
    durable=True,
    routing_key="fin.time_logged.vip.recorded",
    arguments={
        "x-max-priority": 10,
        "x-dead-letter-exchange": "pm.dlx",
        "x-dead-letter-routing-key": "fin.time_logged.vip.dead",
    },
)
