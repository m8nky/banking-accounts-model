import logging
import sys

logging.getLogger().setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)

# Disable debug message for 'chardet' and 'urllib3'
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('chardet').setLevel(logging.WARNING)

c = {}
c['DISPATCH_CONFIG_FILE'] = 'job.json'
c['DRYRUN'] = False
