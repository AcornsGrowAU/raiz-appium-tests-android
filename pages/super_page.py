from appium.webdriver.common.appiumby import AppiumBy
from config.settings import DEFAULT_WAIT
from pages.base_page import BasePage


class SuperPage(BasePage):
    """Raiz Super.

    The test account's super is set up but unfunded ($0), so raiz://raiz_super
    opens onboarding interstitials rather than a funded dashboard:
      1. Insurance opt-in — compliance text + "Apply for insurance" / "Not now"
      2. "Your Raiz Invest Super is Ready" — next steps + "Finish"
    We cover both, and only ever tap the SAFE actions ("Not now"). We never tap
    "Apply for insurance" or "Consolidate my super funds" — those are real,
    irreversible member actions.
    """
    # 1. Insurance interstitial
    INSURANCE_TITLE = (AppiumBy.XPATH, "//*[@text='Insurance cover']")
    INSURANCE_CONSENT_TEXT = (AppiumBy.XPATH, "//*[contains(@text,'Death and TPD')]")
    APPLY_INSURANCE = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Apply for insurance']]")
    NOT_NOW = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Not now']]")

    # 2. Readiness screen
    CONGRATS = (AppiumBy.XPATH, "//*[@text='Congratulations!']")
    READY_TITLE = (AppiumBy.XPATH, "//*[contains(@text,'Super is Ready')]")
    FINISH = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Finish']]")
    CONSOLIDATE = (AppiumBy.XPATH, "//*[@clickable='true'][.//android.widget.TextView[@text='Consolidate my super funds']]")

    # Generic super branding shown across onboarding states (insurance, ready,
    # consolidation/contact). Super onboarding is STATEFUL on a shared account, so
    # is_loaded() must recognise any of these surfaces, not one specific step.
    SUPER_TITLE = (AppiumBy.XPATH, "//*[@text='Raiz Invest Super' or @text='Raiz Super']")
    ANY_SUPER_SURFACE = (AppiumBy.XPATH,
        "//*[@text='Raiz Invest Super' or @text='Raiz Super' or @text='Insurance cover' "
        "or @text='Congratulations!' or contains(@text,'Super is Ready') "
        "or contains(@text,'existing Super funds')]")

    def is_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.ANY_SUPER_SURFACE, timeout=timeout)

    def is_insurance_interstitial(self) -> bool:
        return self.is_present_now(self.APPLY_INSURANCE) and self.is_present_now(self.NOT_NOW)

    def tap_not_now(self):
        self.click(self.NOT_NOW)

    def is_ready_screen(self, timeout=DEFAULT_WAIT) -> bool:
        return self.is_visible(self.READY_TITLE, timeout=timeout) or self.is_visible(self.CONGRATS, timeout=2)

    # --- Account info sub-screen (raiz://raiz_super/account_info) ---
    # Member/account reference details. Not yet crawled — locators are inferred
    # from the standard Raiz Super account-info copy (WATCH on first run).
    ACCOUNT_INFO_TITLE = (AppiumBy.XPATH,
        "//*[@text='Account information' or @text='Account info' "
        "or contains(@text,'Account details') or contains(@text,'Member')]")
    USI_LABEL = (AppiumBy.XPATH, "//*[contains(@text,'USI')]")
    MEMBER_NUMBER_LABEL = (AppiumBy.XPATH,
        "//*[contains(@text,'Member number') or contains(@text,'Member Number')]")
    ABN_LABEL = (AppiumBy.XPATH, "//*[contains(@text,'ABN')]")

    def is_account_info_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return (self.is_visible(self.ACCOUNT_INFO_TITLE, timeout=timeout)
                or self.is_present_now(self.USI_LABEL)
                or self.is_present_now(self.MEMBER_NUMBER_LABEL)
                or self.is_loaded(timeout=2))

    # --- Important documents sub-screen (raiz://raiz_super/important_documents) ---
    # PDS / TMD / financial-services-guide links. Inferred copy (WATCH on first run).
    DOCS_TITLE = (AppiumBy.XPATH,
        "//*[@text='Important documents' or @text='Important Documents' "
        "or contains(@text,'Documents')]")
    DOC_LINKS = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView["
        "contains(@text,'PDS') or contains(@text,'Product Disclosure') "
        "or contains(@text,'Target Market') or contains(@text,'Guide') "
        "or contains(@text,'Statement') or contains(@text,'Policy')]]")
    DOC_TEXTS = (AppiumBy.XPATH,
        "//android.widget.TextView[contains(@text,'PDS') or contains(@text,'Product Disclosure') "
        "or contains(@text,'Target Market') or contains(@text,'Guide') "
        "or contains(@text,'Statement') or contains(@text,'Policy') "
        "or contains(@text,'Disclosure')]")

    def is_docs_loaded(self, timeout=DEFAULT_WAIT) -> bool:
        return (self.is_visible(self.DOCS_TITLE, timeout=timeout)
                or self.is_present_now(self.DOC_TEXTS)
                or self.is_loaded(timeout=2))

    def get_document_texts(self) -> list[str]:
        return [el.text for el in self.driver.find_elements(*self.DOC_TEXTS) if el.text]
