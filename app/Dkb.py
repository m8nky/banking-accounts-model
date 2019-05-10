#!/usr/bin/env python3
import logging
import re
from robobrowser import RoboBrowser

import config

class Dkb:
    BASEURL = 'https://www.dkb.de'
    SERVICE_LOGIN = '/-'
    SERVICE_FINANCIAL_STATUS = '/DkbTransactionBanking/content/banking/financialstatus/FinancialComposite/FinancialStatus.xhtml'

    ACCTYPE_CHECKING = 'CHECKING'
    ACCTYPE_CREDITCARD = 'CREDITCARD'

    # Source: DKB IBAN
    # Target: DKB IBAN
    TRANSACTIONTYPE_CHECKING_CHECKING_LOCAL = 'CHECKING_CHECKING_LOCAL'
    # Source: DKB IBAN
    # Target: Other bank IBAN
    TRANSACTIONTYPE_CHECKING_CHECKING_REMOTE = 'CHECKING_CHECKING_REMOTE'
    # Source: DKB IBAN
    # Target: DKB CreditCard
    TRANSACTIONTYPE_CHECKING_CREDITCARD = 'CHECKING_CREDITCARD'
    # Source: DKB CreditCard
    # Target: DKB IBAN
    TRANSACTIONTYPE_CREDITCARD_CHECKING = 'CREDITCARD_CHECKING'

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        browser = RoboBrowser(parser='lxml')
        browser.open(Dkb.BASEURL + Dkb.SERVICE_LOGIN)
        if browser.state.response.status_code != 200:
            msg = str(browser.state.response.status_code) + " - " + browser.state.response.reason
            self._logger.error("ERROR: Can not open website: " + msg)
            raise WebsiteNotLoadable(msg)
        self._browser = browser
        self._loggedIn = False
        self._accounts = None

    def login(self, userid, pin):
        self._logger.info("Starting login as user %s...", userid)
        form = self._browser.get_form(id='login')
        if not form:
            msg = "Login form not found. Probably the website changed."
            self._logger.error("ERROR: " + msg)
            raise WebsiteNotLoadable(msg)
        form['j_username'].value = userid
        form['j_password'].value = pin
        form['jsEnabled'].value = "false"
        form['browserName'].value = "Firefox"
        form['browserVersion'].value = "40"
        form['screenWidth'].value = "1024"
        form['screenHeight'].value = "768"
        form['osName'].value = "Windows"
        self._browser.submit_form(form)
        if self._browser.state.response.status_code != 200 or not re.search(r'/DkbTransactionBanking/content/banking/financialstatus/FinancialComposite/FinancialStatus.xhtml', self._browser.state.response.url):
            msg = "Login failed :-("
            self._logger.error("ERROR: " + msg)
            return False
        self._logger.info("Login successful.")
        self._loggedIn = True
        # Fetch list of available accounts
        self._getAccounts()
        return True

    def logout(self):
        if not self._loggedIn:
            return
        logout = self._browser.find("a", id="logout")
        self._browser.follow_link(logout)
        if self._browser.state.response.status_code != 200:
            msg = "Logout failed, something went wrong."
            self._logger.error("ERROR: " + msg)
            raise WebsiteNotLoadable(msg)
        self._logger.info("Logout successful. Session finished.")
        self._loggedIn = False

    def getBalance(self, account):
        assert account in self._accounts
        return self._accounts[account]['balance']

    def remittance(self, source, target, amount, creditorName=None, purpose=None):
        # Sanitize input
        assert source in self._accounts
        assert re.match(r'([A-Z]{2}[0-9]{20})|([0-9]{4}\*{8}[0-9]{4})', target)
        transaction_type = None
        if source in self._accounts and self._accounts[source]['type'] == Dkb.ACCTYPE_CHECKING:
            if not target in self._accounts:
                transaction_type = Dkb.TRANSACTIONTYPE_CHECKING_CHECKING_REMOTE
            elif self._accounts[target]['type'] == Dkb.ACCTYPE_CHECKING:
                transaction_type = Dkb.TRANSACTIONTYPE_CHECKING_CHECKING_LOCAL
            elif self._accounts[target]['type'] == Dkb.ACCTYPE_CREDITCARD:
                transaction_type = Dkb.TRANSACTIONTYPE_CHECKING_CREDITCARD
        if source in self._accounts and self._accounts[source]['type'] == Dkb.ACCTYPE_CREDITCARD:
            if target in self._accounts and self._accounts[target]['type'] == Dkb.ACCTYPE_CHECKING:
                transaction_type = Dkb.TRANSACTIONTYPE_CREDITCARD_CHECKING
        assert transaction_type is not None
        # Check parameters
        if transaction_type == Dkb.TRANSACTIONTYPE_CHECKING_CHECKING_REMOTE:
            assert type(creditorName) is str and len(creditorName) > 0
            assert type(purpose) is str and len(purpose) > 0
        if transaction_type == Dkb.TRANSACTIONTYPE_CHECKING_CHECKING_LOCAL:
            assert type(purpose) is str and len(purpose) > 0
        # Source or target account constellation is not allowed
        amount = Amount(amount)
        # Navigate to account overview and select source account
        self._browser.open(Dkb.BASEURL + Dkb.SERVICE_FINANCIAL_STATUS)
        accountSelector = self._browser.select('tr#gruppe-' + str(self._accounts[source]['group_idx']) + '_' + str(self._accounts[source]['row_idx']))
        if not len(accountSelector) > 0:
            raise WebsiteNotLoadable("Account element not found.")
        # Check if transaction amount is covered by balance
        if not self._accounts[source]['balance'].canCoverTransactionAmount(amount):
            msg = "Balance of account '" + source + "' not sufficient to initiate transaction of " + amount.get() + " EUR."
            self._logger.warning("WARNING: " + msg)
            raise BalanceNotSufficient(msg)
        # Navigate to transaction
        remittance = accountSelector[0].select('a[tid="remittance"]')
        if not len(remittance) > 0:
            raise WebsiteNotLoadable("Remittance element not found for '" + source + "'.")
        self._browser.follow_link(remittance[0])
        if transaction_type == Dkb.TRANSACTIONTYPE_CREDITCARD_CHECKING:
            # For creditcard to checking transactions, skip step 2 - go directly to step 3
            ### Step 3- Amount input and transaction review
            self._creditCardRemittance(amount)
            self._currentTransaction = self._reviewCreditcardToCheckingRemittance()
        else:
            ### Step 2 - Account selector and transaction details
            form = self._browser.get_forms()[2]
            assert form is not None
            # Check if target account is hosted by this DKB account ('own account')
            accountLabel = None
            for al in form['slOwnCreditorAccounts'].labels:
                if re.match(re.sub(r'\*', '', target), re.sub(r'[\s\*]', '', al)):
                    # Success, target account is local
                    accountLabel = al
                    break
            if accountLabel:
                # Select 'own account' (option: 2) transaction
                form['creditorAccountType'].options = ['2']
                form['creditorAccountType'].value = '2'
                # Select target account
                form['slOwnCreditorAccounts'].value = accountLabel
            else:
                # Account is not local - do transaction to another bank
                # Select 'foreign account' (option: 1) transaction
                form['creditorAccountType'].options = ['1']
                form['creditorAccountType'].value = '1'
                # Fill in target account information
                form['creditorName'].value = creditorName
                form['creditorAccountNo'].value = target
            # Submit and proceed with step 3
            self._browser.submit_form(form)
            ### Step 3 - Amount input and transaction review
            if transaction_type == Dkb.TRANSACTIONTYPE_CHECKING_CREDITCARD:
                # Target account is creditcard
                self._creditCardRemittance(amount)
                self._currentTransaction = self._reviewCheckingToCreditcardRemittance()
            else:
                # transaction_type in [ Dkb.TRANSACTIONTYPE_CHECKING_CHECKING_LOCAL, Dkb.TRANSACTIONTYPE_CHECKING_CHECKING_REMOTE ]
                # Target account is checking
                self._checkingRemittance(amount, purpose)
                self._currentTransaction = self._reviewCheckingRemittance()
        return self._currentTransaction

    def approveCurrentTransaction(self, source, target, amount, tan=None):
        if source != self._currentTransaction['source'] or target != self._currentTransaction['target'] or amount != self._currentTransaction['amount']:
            msg = "Requested transaction commit is invalid '" + source + "' => '" + target + "' (" + amount + ")."
            self._logger.error("ERROR: " + msg)
            assert False
        if not config.c['DRYRUN']:
            form = self._browser.get_forms()[2]
            assert form is not None
            # Fill in TAN, if needed
            if target not in self._accounts or (self._accounts[source]['type'] == Dkb.ACCTYPE_CHECKING and self._accounts[target]['type'] == Dkb.ACCTYPE_CHECKING):
                assert tan
                form['tan'].value = tan
            self._browser.submit_form(form)
            successBlock = self._browser.find(class_=re.compile(r'successBox', re.I))
            if not successBlock:
                msg = "Transaction failed for '" + source + "' => '" + target + "' (" + amount + ")."
                self._logger.error("ERROR: " + msg)
                raise TransactionFailed(msg)
            msg = successBlock.ul.li.text
            self._logger.info("Transaction successful: " + msg)
        else:
            self._logger.info("DRYRUN transaction successful: " + str(tan))
        return True

    def _getAccounts(self):
        checkingTypes = [ "Girokonto" ]
        creditcardTypes = [ "Kreditkarte", "DKB-VISA-Tagesgeld" ]
        if not self._loggedIn:
            return None
        self._browser.open(Dkb.BASEURL + Dkb.SERVICE_FINANCIAL_STATUS)
        accounts = {}
        row_idx = 0
        group_idx = 0
        while True:
            # Test if another account exists.
            accountSelector = self._browser.select('tr#gruppe-' + str(group_idx) + '_' + str(row_idx))
            if not len(accountSelector) > 0:
                if row_idx == 0:
                    break
                row_idx = 0
                group_idx += 1
                continue
            # Extract account information.
            ## Account type
            accountType = accountSelector[0].select('td div.forceWrap')
            if not len(accountType) > 0:
                raise WebsiteNotLoadable("Website element not found.")
            accountType = accountType[0].string.strip()
            if accountType in checkingTypes:
                accountType = Dkb.ACCTYPE_CHECKING
            elif accountType in creditcardTypes:
                accountType = Dkb.ACCTYPE_CREDITCARD
            else:
                msg = "Account type '" + accountType + "' can not be mapped. Exiting."
                self._logger.error("ERROR: " + msg)
                raise WebsiteNotLoadable(msg)
            ## IBAN or card number
            iban = accountSelector[0].select('td div.iban')
            if not len(iban) > 0:
                raise WebsiteNotLoadable("Website element not found.")
            iban = iban[0].string.strip()
            iban = re.sub(r'\s', '', iban)
            assert len(iban) > 0
            ## Current balance
            balance = accountSelector[0].select('td.amount span')
            if not len(balance) > 0:
                raise WebsiteNotLoadable("Website element not found.")
            balance = Amount(balance[0].string.strip())
            # Assemble account status
            self._logger.info("Account: " + accountType + " - " + iban + " - " + balance.get())
            accounts[iban] = {
                'type': accountType,
                'balance': balance,
                'group_idx': group_idx,
                'row_idx': row_idx
            }
            row_idx += 1
        self._accounts = accounts

    def _creditCardRemittance(self, amount):
        # Select 'amount' form
        form = self._browser.get_forms()[2]
        assert form is not None
        form['amountToTransfer'].value = amount.get()
        self._browser.submit_form(form)

    def _checkingRemittance(self, amount, purpose):
        # Select 'amount' and 'purpose' form
        form = self._browser.get_forms()[2]
        assert form is not None
        form['amountToTransfer'].value = amount.get()
        form['paymentPurposeLine'].value = purpose
        self._browser.submit_form(form)

    def _reviewCheckingToCreditcardRemittance(self):
        result = {}
        # Select approval fields for review
        value = self._browser.find(id='outOrderingCustomerAccount')
        assert value
        result['source'] = self._extractIbanOrCreditcardNumber(value.string)
        value = self._browser.find(id='outOwnPayeeAccount')
        assert value
        result['target'] = self._extractIbanOrCreditcardNumber(value.string)
        value = self._browser.find(id='outAmountToTransfer')
        assert value
        result['amount'] = value.string.strip()
        self._logger.info("Review transaction: " + str(result))
        return result

    def _reviewCheckingRemittance(self):
        result = {}
        # Select approval fields for review
        value = self._browser.find(id='outOrderingCustomerAccount.accountNo')
        assert value
        result['source'] = self._extractIbanOrCreditcardNumber(value.string)
        value = self._browser.find(id='outCreditorAccountNo')
        assert value
        result['target'] = self._extractIbanOrCreditcardNumber(value.string)
        value = self._browser.find(id='outAmountToTransfer')
        assert value
        result['amount'] = value.string.strip()
        result['tan'] = True
        self._logger.info("Review transaction: " + str(result))
        return result

    def _reviewCreditcardToCheckingRemittance(self):
        result = {}
        # Select approval fields for review
        value = self._browser.select('#form1434775544_1 > fieldset:nth-child(2) > p:nth-child(1) > span.col65.floatRight > strong')
        assert len(value) > 0
        result['source'] = self._extractIbanOrCreditcardNumber(value[0].string)
        value = self._browser.select('#form1434775544_1 > fieldset:nth-child(2) > p:nth-child(2) > span.col65.floatRight > strong')
        assert len(value) > 0
        result['target'] = self._extractIbanOrCreditcardNumber(value[0].string)
        value = self._browser.select('#form1434775544_1 > fieldset:nth-child(2) > p:nth-child(3) > span.col65.floatRight > strong')
        assert len(value) > 0
        value = value[0].string
        value = re.sub(r'&nbsp;', ' ', value)
        result['amount'] = value
        return result

    def _extractIbanOrCreditcardNumber(self, value):
        value = value.strip()
        value = re.sub(r'\s', '', value)
        value = re.sub(r'(.*)/.*', '\g<1>', value)
        return value


class Amount:
    def __init__(self, amount):
        # Input as int means expects full EUR only, no cents. ',00' will be appended.
        if type(amount) is int:
            self._amount = str(amount) + '00'
        # Input as str expects EUR and cents, e.g. 23,00 or 23.50
        elif type(amount) is str:
            assert type(amount) is str and len(amount) >= 3
            self._amount = re.sub(r'[\.,]', '', amount)
        else:
            assert False

    def get(self, decimalSeparator=','):
        # Return amount string
        assert decimalSeparator in [ ',', '.' ]
        amount = self._amount
        amount = re.sub(r'-', '', amount)
        amount = amount[::-1]
        # Insert decimal separator
        amount = amount[:2] + decimalSeparator + amount[2:]
        amount = amount[::-1]
        amount = '-' + amount if not self._isPositive() else amount
        return amount

    def _isPositive(self):
        return False if re.match(r'-', self._amount) else True

    def canCoverTransactionAmount(self, amount):
        if not isinstance(amount, Amount):
            if type(amount) == int:
                amount = str(amount) + '00'
            amount = Amount(str(amount))
        return int(self._amount) > int(amount._amount)

class WebsiteNotLoadable(Exception):
    pass

class BalanceNotSufficient(Exception):
    pass

class TransactionFailed(Exception):
    pass
