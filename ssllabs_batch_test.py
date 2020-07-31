import json
import logging
import optparse
import os
import requests
import time
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

VERSION = "1.0"

## SSLLABS API v3 STUFF ##
SSLLABS_API_MAINENDPOINT = "https://api.ssllabs.com/api/v3/"
SSLLABS_API_INFO_ENDPOINT = "info"
SSLLABS_API_INFO_PARAMS = None
SSLLABS_API_ANALYZE_ENDPOINT = "analyze"
SSLLABS_API_ANALYZE_INITIAL_PARAMS = {"publish": "off", "startNew": "on", "fromCache": "off", "all": "done", "ignoreMismatch": "off"}
SSLLABS_API_ANALYZE_POLLING_PARAMS = {"publish": "off", "startNew": "off", "fromCache": "off", "all": "done", "ignoreMismatch": "off"}
SSLLABS_API_ANALYZE_ENDPOINT_READY_STATUS = "READY"
SSLLABS_API_ANALYZE_ENDPOINT_INPROGRESS_STATUS = "IN_PROGRESS"
SSLLABS_API_ANALYZE_ENDPOINT_ERROR_STATUS = "ERROR"
SSLLABS_API_ANALYZE_ENDPOINT_DNS_STATUS = "DNS"

POLLING_TIMEOUT = 10
POLLING_MAX_RETRIES = 720

## ARGS STUFF ##
parser = optparse.OptionParser()
parser.add_option("-l", action = "store", dest = "in_file", help = "File with a list of endpoints to test")
parser.add_option("-q", action = "store_true", dest = "quiet", default = False, help = "Quiet mode (don't output to stdout)")
parser.add_option("-v", action = "store_true", dest = "verbose", default = False, help = "Verbose (debug) mode")
options, args = parser.parse_args()

## LOGGING STUFF ##
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s\t[%(levelname)s]\t%(message)s')
logfile_handler = RotatingFileHandler("ssllabs_batch_test.log", maxBytes=10000000, backupCount=10)
logfile_handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG if options.verbose else logging.INFO)
logger.addHandler(logfile_handler)
if not options.quiet:
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

## MAKE SSLLABS API REQUEST ##
def api_request(req_endpoint, req_params):
    try:
        r = requests.get(url = "%s%s" % (SSLLABS_API_MAINENDPOINT, req_endpoint), params = req_params)
        logger.debug("func:api_request\tr.text:%s" % r.text)
        if r.status_code == 200:
            logger.info("Requested URL: '%s'; HTTP Status: %d" % (r.url, r.status_code))
            return r.json()
        else:
            logger.error("Requested URL: '%s'; HTTP Status: %d" % (r.url, r.status_code))
            return None
    except Exception as e:
        logger.error(traceback.format_exc())

## DO A FULL TEST ON A GIVEN URL ##
def test_url(url):
    SSLLABS_API_ANALYZE_INITIAL_PARAMS["host"] = url
    logger.info("Starting test on '%s'. Please wait..." % url)
    analyze_data = api_request(SSLLABS_API_ANALYZE_ENDPOINT, SSLLABS_API_ANALYZE_INITIAL_PARAMS)
    if analyze_data["status"] in [SSLLABS_API_ANALYZE_ENDPOINT_INPROGRESS_STATUS, SSLLABS_API_ANALYZE_ENDPOINT_DNS_STATUS]:
        retries = 0
        while (retries < POLLING_MAX_RETRIES and analyze_data["status"] != SSLLABS_API_ANALYZE_ENDPOINT_READY_STATUS):
            logger.info("Waiting %d seconds until next polling..." % POLLING_TIMEOUT)
            time.sleep(POLLING_TIMEOUT)
            SSLLABS_API_ANALYZE_POLLING_PARAMS["host"] = url
            analyze_data = api_request(SSLLABS_API_ANALYZE_ENDPOINT, SSLLABS_API_ANALYZE_POLLING_PARAMS)
            if analyze_data["status"] in [SSLLABS_API_ANALYZE_ENDPOINT_INPROGRESS_STATUS, SSLLABS_API_ANALYZE_ENDPOINT_DNS_STATUS]:
                logger.info("Host status (%s:%d): %s" % (analyze_data["host"], analyze_data["port"], analyze_data["status"]))
                for e in analyze_data["endpoints"]:
                        logger.info("\tEndpoint status (%s%s): %s [Progress: %s%%; ETA: %ssecs]" % (e["ipAddress"], "/%s" % e["serverName"] if "serverName" in e else "", e["statusMessage"], str(e["progress"]) if "progress" in e else "--", str(e["eta"]) if "eta" in e else "--"))
            elif analyze_data["status"] == SSLLABS_API_ANALYZE_ENDPOINT_ERROR_STATUS:
                logger.error("SSLLabs returned an error: %s" % analyze_data["statusMessage"])
                break
            retries += 1

        if analyze_data["status"] == SSLLABS_API_ANALYZE_ENDPOINT_READY_STATUS:
            logger.info("Test finished for %s:%d." % (analyze_data["host"], analyze_data["port"]))
            return analyze_data
        else:
            logger.error("Giving up on testing %s:%d." % (analyze_data["host"], analyze_data["port"]))
            return None
    elif analyze_data["status"] == SSLLABS_API_ANALYZE_ENDPOINT_ERROR_STATUS:
            logger.error("SSLLabs returned an error: %s" % analyze_data["statusMessage"])
            return None

## MAIN ##
if __name__ == "__main__":
    if options.in_file and os.path.isfile(options.in_file):
        logger.info("ssllabs_batch_test v%s starting..." % VERSION)
        logger.info("Testing SSLLabs engine availability")
        info_data = api_request(SSLLABS_API_INFO_ENDPOINT, SSLLABS_API_INFO_PARAMS)
        if info_data:
            logger.info("SSLLabs engine OK. More info:")
            logger.info("\tSSL Labs software version: '%s'" % info_data["engineVersion"])
            logger.info("\tRating criteria version: '%s'" % info_data["criteriaVersion"])
            logger.info("\tMaximum number of concurrent assessments: '%s'" % info_data["maxAssessments"])
            logger.info("\tNumber of ongoing assessments submitted: '%s'" % info_data["currentAssessments"])
            logger.info("\tCool-off period after each new assessment (ms): '%s'" % info_data["newAssessmentCoolOff"])
            logger.info("\tMessages:")
            for m in range(len(info_data["messages"])):
                logger.info("\t\tMessage %d: '%s'" % (m+1, info_data["messages"][m]))
            with open(options.in_file) as f_in:
                for url in f_in:
                    url = url.rstrip()
                    analyze_data = test_url(url)
                    with open("%s_%s.json" % (datetime.now().strftime("%Y_%m_%d_%H_%M_%S"), url), "w") as f_out:
                        f_out.write(json.dumps(analyze_data, indent=4))

        else:
            logger.fatal("Error checking SSLLabs engine availability. Exiting.")
            os.sys.exit(-1)
    else:
        logger.fatal("Invalid input file (-l). Exiting.")
        os.sys.exit(-1)
