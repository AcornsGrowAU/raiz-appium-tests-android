"""Temporary timing instrumentation for BasePage. Auto-loaded by conftest when
PROFILE_TESTS=1 is set. Logs every wait/probe with wall-clock duration and
locator preview so we can see where the suite spends its time.

Output goes to /tmp/raiz_profile.log to keep pytest stdout clean.
"""
import os
import time
import functools

LOG_PATH = os.environ.get("RAIZ_PROFILE_LOG", "/tmp/raiz_profile.log")


def _short(locator):
    try:
        by, value = locator
        v = value if len(value) < 80 else value[:77] + "..."
        return f"{by}={v}"
    except Exception:
        return repr(locator)


def install():
    from pages.base_page import BasePage

    if getattr(BasePage, "_profile_installed", False):
        return
    BasePage._profile_installed = True

    open(LOG_PATH, "w").close()

    def log(line: str):
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")

    log(f"# session start ts={time.time():.3f}")

    def wrap(name, fn, locator_arg_index=1):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            t0 = time.perf_counter()
            outcome = "ok"
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, bool) and not result:
                    outcome = "false"
                return result
            except Exception as e:
                outcome = f"err:{type(e).__name__}"
                raise
            finally:
                dt = time.perf_counter() - t0
                if len(args) > locator_arg_index:
                    loc = _short(args[locator_arg_index])
                else:
                    loc = "?"
                timeout = kwargs.get("timeout", "")
                log(f"{dt:6.2f}s {name:<14} {outcome:<6} t={timeout!s:>5} {loc}")
        return inner

    BasePage.find = wrap("find", BasePage.find)
    BasePage.find_clickable = wrap("find_clickable", BasePage.find_clickable)
    BasePage.is_visible = wrap("is_visible", BasePage.is_visible)
    BasePage.is_present = wrap("is_present", BasePage.is_present)
    BasePage.is_present_now = wrap("is_present_now", BasePage.is_present_now)
    BasePage.click_present = wrap("click_present", BasePage.click_present)


if os.environ.get("PROFILE_TESTS") == "1":
    install()
