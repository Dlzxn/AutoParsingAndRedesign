import logging

logging.basicConfig(filename = "Data/logs.txt", level = logging.DEBUG, filemode = "w", format =
"%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


