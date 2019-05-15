import logging
import json
import re

from config import c

class Job:
    JOB_NAME = "Name"
    JOB_SHARE = "Share"
    JOB_SHAREVALUE = "ShareValue"
    JOB_SOURCEACCOUNT = "SourceAccount"
    JOB_TARGETACCOUNT = "TargetAccount"
    JOB_REMITTEE = "Remittee"
    JOB_DESCRIPTION = "Description"

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        try:
            fp = open(c['DISPATCH_CONFIG_FILE'], 'r', encoding='utf-8')
            d = json.load(fp)
            fp.close()
            assert 'dispatch' in d
        except Exception as e:
            self._logger.error("ERROR: Reading job config file '" + c['DISPATCH_CONFIG_FILE'] + "' (" + str(e) + ").")
            raise
        self._jobs = d['dispatch']
        assert self._validate()

    def getJobs(self):
        return self._jobs

    def hasRelativeShare(self):
        return True in [ Job.JOB_SHARE in job for job in self._jobs ]

    def calculateShareValue(self, income):
        self._logger.info("## Calculate job amounts.")
        for job in self._jobs:
            if not Job.JOB_SHAREVALUE in job:
                job[Job.JOB_SHAREVALUE] = income * job[Job.JOB_SHARE] // 100

    def _validate(self):
        valid = True
        sumShare = 0
        for j in self._jobs:
            if not (Job.JOB_NAME in j and Job.JOB_SOURCEACCOUNT in j and ((Job.JOB_SHARE in j) ^ (Job.JOB_SHAREVALUE in j)) and Job.JOB_TARGETACCOUNT in j):
                self._logger.error("'job.json' is invalid: Missing fields.")
                valid = False
                continue
            if len(j[Job.JOB_NAME]) <= 0:
                self._logger.error("'job.json' is invalid: Job name not set.")
                valid = False
                continue
            reAccount = re.compile(r'([A-Z]{2}\d{20})|(\d{4}\*{8}\d{4})')
            if not reAccount.match(j[Job.JOB_SOURCEACCOUNT]) or not reAccount.match(j[Job.JOB_TARGETACCOUNT]):
                self._logger.error("'job.json' is invalid: TargetAccount or SourceAccount missing or invalid.")
                valid = False
                continue
            if Job.JOB_SHARE in j:
                sumShare += j[Job.JOB_SHARE]
        if sumShare > 100:
            self._logger.error("'job.json' is invalid: Sum of shares is greater than 100%")
            valid = False
        return valid
