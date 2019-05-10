import logging
import json

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
        for j in self._jobs:
            if not (Job.JOB_NAME in j and Job.JOB_SOURCEACCOUNT in j and ((Job.JOB_SHARE in j) ^ (Job.JOB_SHAREVALUE in j)) and Job.JOB_TARGETACCOUNT in j):
                valid = False
        return valid
