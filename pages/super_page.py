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

    # --- Super History summary (SuperHistoryScreen) ------------------------- #
    # On a FUNDED/activated super, raiz://raiz_super lands on the Super Home
    # dashboard, which carries a "History" card whose "History Details" button
    # (raiz_super_history_details) opens SuperHistoryScreen. That screen shows a
    # summary block (SuperHistorySummary) of clickable rows: Employer
    # Contributions, Your Contributions, Reinvested Dividends, the returns row,
    # and Rollover — each opening an info dialog when tapped.
    #
    # RAIZ-10889 (release 2.41.2): the returns row + its info dialog title are
    # renamed "Market Returns" -> "Total Returns" (the underlying value,
    # gains.total.netReturnAmount, is unchanged). Grounded in app source:
    #   raizFeatureSuper/.../history/summary/SuperHistorySummary.kt (the row)
    #   raizFeatureSuper/.../history/SuperHistoryViewModel.kt#onMarketClick (dialog)
    #   raizFeatureSuper/src/main/res/values/strings.xml
    #     raiz_super_history_market_returns / card_dialog_title_market_returns
    HISTORY_DETAILS_BUTTON = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='History Details']]")
    HISTORY_DETAILS_TEXT = (AppiumBy.XPATH, "//android.widget.TextView[@text='History Details']")

    # Stable, UNCHANGED sibling rows of the summary. These anchor "the History
    # summary surface is on screen" independently of the returns-row rename, so
    # the label assertion can only pass when the surface is actually present
    # (never vacuously) and fails if the row still says "Market Returns".
    HISTORY_SUMMARY_ANCHOR = (AppiumBy.XPATH,
        "//android.widget.TextView[@text='Employer Contributions' "
        "or @text='Reinvested Dividends' or @text='Rollover']")

    # RAIZ-10889 — the renamed row label and its retired predecessor. Exact-text
    # match so it never collides with the main portfolio's "Total returns:" /
    # "Market return to date:" (different strings, trailing colon).
    TOTAL_RETURNS_LABEL = (AppiumBy.XPATH, "//android.widget.TextView[@text='Total Returns']")
    MARKET_RETURNS_LABEL = (AppiumBy.XPATH, "//android.widget.TextView[@text='Market Returns']")
    # The whole row is clickable (onMarketClick) and opens the info dialog.
    TOTAL_RETURNS_ROW = (AppiumBy.XPATH,
        "//*[@clickable='true'][.//android.widget.TextView[@text='Total Returns']]")

    # Info dialog opened by tapping the returns row. Its title is renamed to
    # "Total Returns"; the help body keeps the distinctive "Total gain/loss…"
    # copy (card_dialog_message_market_returns) that proves the dialog opened.
    # TODO(device): confirm the dialog container id/structure on 2.41.2 — the
    # title node may need scoping to the dialog if the row label leaks into the
    # match; the message substring below is the device-independent open-proof.
    RETURNS_DIALOG_MESSAGE = (AppiumBy.XPATH,
        "//*[contains(@text,'Total gain/loss shows how your investments')]")

    def open_history_summary(self, timeout=DEFAULT_WAIT) -> bool:
        """Best-effort: from the current Super surface, reach the History summary
        (SuperHistoryScreen) that carries the returns row.

        On a funded super this taps the Super Home "History Details" button; on
        the shared UNFUNDED test account raiz://raiz_super lands on onboarding and
        neither the button nor the summary exists. Returns True once a stable
        summary anchor row is on screen, False otherwise (caller should skip).
        """
        if self.is_present_now(self.HISTORY_SUMMARY_ANCHOR):
            return True
        if not self.is_present_now(self.HISTORY_DETAILS_TEXT):
            # The History card can sit below the fold on the Super Home dashboard.
            try:
                self.scroll_to_text("History Details")
            except Exception:
                pass
        if self.is_present(self.HISTORY_DETAILS_TEXT, timeout=timeout):
            try:
                self.click(self.HISTORY_DETAILS_BUTTON)
            except Exception:
                self.click_present(self.HISTORY_DETAILS_TEXT)
            return self.is_present(self.HISTORY_SUMMARY_ANCHOR, timeout=timeout)
        return False

    def open_returns_info_dialog(self, timeout=DEFAULT_WAIT) -> bool:
        """Tap the (renamed) returns row to open its info dialog. The whole row is
        clickable — not just the info icon — so tapping the row opens the dialog.
        Returns True once the dialog's distinctive help copy renders. Best-effort:
        False if the row/dialog can't be resolved (e.g. layout differs on-device)."""
        row = self.TOTAL_RETURNS_ROW if self.is_present_now(self.TOTAL_RETURNS_ROW) \
            else self.TOTAL_RETURNS_LABEL
        try:
            self.click_present(row)
        except Exception:
            return False
        return self.is_present(self.RETURNS_DIALOG_MESSAGE, timeout=timeout)
