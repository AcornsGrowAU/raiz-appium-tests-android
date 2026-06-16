"""
All registered deep links for the Raiz AU app.
Use DeepLinks.open(driver, DeepLinks.HOME) to navigate directly to any screen.
"""

SCHEME = "raiz://"


class DeepLinks:
    HOME = "raiz://home"
    HISTORY = "raiz://history"
    FUTURE = "raiz://future"
    WITHDRAW = "raiz://withdraw"
    DEPOSIT = "raiz://deposit"
    FINANCE = "raiz://finance"
    PERFORMANCE = "raiz://performance"
    PERFORMANCE_DAY = "raiz://performance/day"
    PERFORMANCE_MONTH = "raiz://performance/month"
    PORTFOLIO = "raiz://portfolio"
    PORTFOLIO_CUSTOM = "raiz://portfolio/custom"
    RAIZ_KIDS = "raiz://raiz_kids"
    RAIZ_KIDS_2 = "raiz://raiz_kids_2"
    RAIZ_SUPER = "raiz://raiz_super"
    RAIZ_SUPER_ACCOUNT_INFO = "raiz://raiz_super/account_info"
    RAIZ_SUPER_IMPORTANT_DOCS = "raiz://raiz_super/important_documents"
    RECURRING_INVESTMENTS = "raiz://recurring_investments"
    INVITE_FRIENDS = "raiz://invite_friends"
    REWARDS = "raiz://raiz_rewards"
    REWARDS_LINKED_ACCOUNTS = "raiz://rewards_linked_accounts"
    REWARDS_AUTO = "raiz://rewards_auto"
    ROUND_UPS = "raiz://round_ups"
    ROUND_UPS_SETTINGS = "raiz://round_ups/settings"
    ROUND_UPS_ACCOUNTS = "raiz://accounts/round_ups"
    FUNDING_ACCOUNT = "raiz://funding_account"
    SPENDING_ACCOUNT = "raiz://spending_account"
    OFFSETTERS = "raiz://offsetters"
    BLOG = "raiz://blog"
    PROFILE_PERSONAL = "raiz://profile/personal"
    PROFILE_FINANCIAL = "raiz://profile/financial"
    INVEST = "raiz://invest"
    ACHIEVEMENTS = "raiz://achievements"
    JARS = "raiz://jars"
    DIVIDENDS = "raiz://dividends"
    PLANS = "raiz://plans"
    FEES = "raiz://fees"
    NOTIFICATIONS_SETTINGS = "raiz://notifications_settings"
    MILESTONE = "raiz://milestone"
    TRANSACTIONS = "raiz://transactions"
    REWARDS_ACCOUNTS = "raiz://accounts/rewards"
    FINANCIAL_INSIGHTS_ACCOUNTS = "raiz://accounts/financial_insights"

    @staticmethod
    def open(driver, link: str) -> None:
        """Navigate to a screen via deep link. Requires the user to already be logged in."""
        driver.execute_script("mobile: deepLink", {
            "url": link,
            "package": "com.acornsau.android.development",
        })
