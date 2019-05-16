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
#import http.client as http_client
#http_client.HTTPConnection.debuglevel = 1
#logging.getLogger('requests.packages.urllib3').setLevel(logging.DEBUG)
#logging.getLogger('requests.packages.urllib3').propagate = True

c = {}
c['DISPATCH_CONFIG_FILE'] = 'job.json'
c['DRYRUN'] = False
