import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException

LOGIN_URL = "https://client.webhostmost.com/login"

# --- Precise Element Selectors ---
USERNAME_SELECTOR = (By.ID, "inputEmail")
PASSWORD_SELECTOR = (By.ID, "inputPassword")
LOGIN_BUTTON_SELECTOR = (By.ID, "login")

# --- Success Indicators (after login click) ---
SUCCESS_URL_CONTAINS = "clientarea.php"
SUCCESS_TITLE_CONTAINS = "Client Area"
SUCCESS_ELEMENT_SELECTOR = (By.XPATH, "//h1[normalize-space()='Dashboard']")

# --- Failure Indicator (after login click) ---
FAILURE_ELEMENT_SELECTOR = (By.XPATH, "//div[contains(@class, 'alert-danger') and normalize-space()='Login Details Incorrect. Please try again.']")


def setup_driver():
    """配置并返回一个全新的 Selenium WebDriver 实例"""
    options = webdriver.ChromeOptions()
    # 无痕模式相关的参数 (headless 已经提供了很好的隔离性, 但这些可以加强)
    options.add_argument("--incognito") # 明确启用无痕模式
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 确保每次都下载或使用最新的驱动
    # 清理 webdriver-manager 缓存可以强制重新下载，但通常不需要
    # from webdriver_manager.core.utils import WDMCacheManager
    # WDMCacheManager().clear_cache(osName=None, driverName=None, osType=None, driverVersion=None)

    new_driver = None
    try:
        print("Setting up new WebDriver instance...")
        service = ChromeService(ChromeDriverManager().install())
        new_driver = webdriver.Chrome(service=service, options=options)
        print("New WebDriver instance setup successfully.")
    except Exception as e:
        print(f"Critical Error: Could not initialize Chrome WebDriver: {e}")
        raise # 如果驱动无法初始化，则抛出异常，由上层处理
    
    if new_driver:
        new_driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return new_driver

def save_debug_info(driver, username, stage="error"):
    """Saves screenshot and page source for debugging."""
    if not driver:
        print(f"Debug info not saved for {username} at stage '{stage}' because driver is None.")
        return
        
    safe_username = "".join(c if c.isalnum() else "_" for c in username)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = f"{stage}_{safe_username}_{timestamp}.png"
    page_source_path = f"{stage}_source_{safe_username}_{timestamp}.html"

    print(f"Saving debug information for {username} at stage '{stage}'.")
    try:
        print(f"Current URL: {driver.current_url}")
        print(f"Current page title: '{driver.title}'")
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Page source saved to {page_source_path}")
    except Exception as e_dbg:
        print(f"Could not save full debug info: {e_dbg}")


def login_single_account(driver, username, password):
    """执行单个账户的登录操作, 使用传入的 driver 实例"""
    print(f"Attempting to log in as {username} using current browser session...")

    try:
        print(f"Navigating to login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located(USERNAME_SELECTOR)) # 增加等待时间
        
        print(f"Page title after load: '{driver.title}'")
        print(f"Current URL after load: {driver.current_url}")

        print(f"Locating username field with selector: {USERNAME_SELECTOR}")
        username_field = driver.find_element(*USERNAME_SELECTOR)
        print("Username field found. Clearing and sending keys.")
        username_field.clear()
        username_field.send_keys(username)

        print(f"Locating password field with selector: {PASSWORD_SELECTOR}")
        password_field = driver.find_element(*PASSWORD_SELECTOR)
        print("Password field found. Clearing and sending keys.")
        password_field.clear()
        password_field.send_keys(password)
        
        print(f"Attempting to click login button with ID selector: {LOGIN_BUTTON_SELECTOR}")
        try:
            login_button = WebDriverWait(driver, 20).until( # 增加等待时间
                EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR)
            )
            print("Login button found and clickable. Executing click via JS.")
            driver.execute_script("arguments[0].click();", login_button)
        except TimeoutException:
            print(f"Login button (ID: {LOGIN_BUTTON_SELECTOR[1]}) not 'clickable' via explicit wait. Saving debug info.")
            save_debug_info(driver, username, "login_button_unclickable")
            return False
        except (NoSuchElementException, ElementNotInteractableException) as e_click:
            print(f"Could not find or interact with login button (ID: {LOGIN_BUTTON_SELECTOR[1]}): {e_click}")
            save_debug_info(driver, username, "login_button_interaction_fail")
            return False
        
        print("Login button click attempted. Waiting for success or failure indicator (25s timeout)...")
        WebDriverWait(driver, 25).until( # 增加等待时间
            EC.any_of(
                EC.url_contains(SUCCESS_URL_CONTAINS),
                EC.title_contains(SUCCESS_TITLE_CONTAINS),
                EC.visibility_of_element_located(SUCCESS_ELEMENT_SELECTOR),
                EC.visibility_of_element_located(FAILURE_ELEMENT_SELECTOR)
            )
        )

        current_url = driver.current_url
        current_title = driver.title
        dashboard_visible = False
        dashboard_header_text = "Not checked/found"

        try: # Check failure message first
            failure_element = driver.find_element(*FAILURE_ELEMENT_SELECTOR)
            if failure_element.is_displayed():
                print(f"Login failed for {username}. Found failure indicator: '{failure_element.text}'")
                save_debug_info(driver, username, "login_failed_message_explicit")
                return False
        except NoSuchElementException:
            pass 

        try: # Then check success element
            dashboard_header = driver.find_element(*SUCCESS_ELEMENT_SELECTOR)
            if dashboard_header.is_displayed():
                dashboard_visible = True
                dashboard_header_text = dashboard_header.text
        except NoSuchElementException:
            pass 

        if SUCCESS_URL_CONTAINS in current_url and \
           SUCCESS_TITLE_CONTAINS in current_title and \
           dashboard_visible:
            print(f"Successfully logged in as {username}. Conditions met:")
            print(f"  URL: {current_url}")
            print(f"  Title: {current_title}")
            print(f"  Dashboard Header: '{dashboard_header_text}' (Visible: {dashboard_visible})")
            # save_debug_info(driver, username, "login_success") # Optional: save info on success
            return True
        else:
            print(f"Login outcome unclear for {username}. Failure message not seen, but success conditions not fully met.")
            print(f"  URL: {current_url} (Expected part: '{SUCCESS_URL_CONTAINS}')")
            print(f"  Title: {current_title} (Expected part: '{SUCCESS_TITLE_CONTAINS}')")
            print(f"  Dashboard Header Visible: {dashboard_visible} (Expected: {SUCCESS_ELEMENT_SELECTOR}, Text: '{dashboard_header_text}')")
            save_debug_info(driver, username, "login_unclear_conditions")
            return False

    except TimeoutException as te:
        print(f"A TimeoutException occurred during login for {username}: {str(te).splitlines()[0]}")
        save_debug_info(driver, username, "login_timeout_main")
    except NoSuchElementException as nse:
        print(f"A NoSuchElementException occurred for {username}: {str(nse).splitlines()[0]}")
        save_debug_info(driver, username, "login_nosuchelement_main")
    except ElementNotInteractableException as enie:
        print(f"An ElementNotInteractableException occurred for {username}: {str(enie).splitlines()[0]}")
        save_debug_info(driver, username, "login_notinteractable_main")
    except StaleElementReferenceException as sere:
        print(f"A StaleElementReferenceException occurred for {username}: {str(sere).splitlines()[0]}")
        save_debug_info(driver, username, "login_staleelement_main")
    except Exception as e:
        print(f"An unexpected error occurred during login for {username}: {type(e).__name__} - {str(e)}")
        save_debug_info(driver, username, f"login_unexpected_error_{type(e).__name__}")
    return False

def main():
    accounts_json_str = os.environ.get("ACCOUNTS_JSON")
    if not accounts_json_str:
        print("Error: ACCOUNTS_JSON environment variable not set.")
        return

    try:
        accounts = json.loads(accounts_json_str)
    except json.JSONDecodeError:
        print(f"Error: ACCOUNTS_JSON is not valid JSON. Content was: {accounts_json_str}")
        return

    if not isinstance(accounts, list) or not all(isinstance(acc, dict) for acc in accounts):
        print("Error: ACCOUNTS_JSON should be a JSON array of objects (list of dicts).")
        return
    
    if not accounts:
        print("No accounts found in ACCOUNTS_JSON. Exiting.")
        return

    overall_success_count = 0
    failed_accounts = []

    for i, account in enumerate(accounts):
        username = account.get("username")
        password = account.get("password")
        
        print(f"\n--- Processing Account {i+1} of {len(accounts)}: {username} ---")

        if not username or not password:
            print(f"Warning: Skipping account {username} due to missing username or password.")
            failed_accounts.append(f"{username or 'N/A'} (missing credentials)")
            continue
        
        current_driver = None # Initialize driver to None for this account attempt
        try:
            current_driver = setup_driver() # Create a new driver instance for each account
            if not current_driver: # Should not happen if setup_driver raises exception on failure
                 print(f"Failed to setup WebDriver for account {username}. Skipping.")
                 failed_accounts.append(f"{username} (driver setup failed)")
                 continue

            # Optional: Clear cookies for belt-and-suspenders, though new instance should be clean
            # current_driver.delete_all_cookies() 
            
            login_successful = login_single_account(current_driver, username, password)
            
            if login_successful:
                overall_success_count += 1
                print(f"Successfully processed account: {username}")
                # Add any post-login actions here using current_driver
                # e.g., current_driver.get("https://client.webhostmost.com/clientarea.php?action=services")
                # time.sleep(5)
            else:
                failed_accounts.append(username)
                print(f"Failed to process account: {username}")

        except Exception as e_outer: # Catch errors from setup_driver or unexpected issues in the loop
            print(f"A critical error occurred while processing account {username}: {type(e_outer).__name__} - {e_outer}")
            failed_accounts.append(f"{username} (critical error: {type(e_outer).__name__})")
            if current_driver: # If driver exists but error happened outside login_single_account
                save_debug_info(current_driver, username, "account_loop_critical_error")
        finally:
            if current_driver:
                current_driver.quit()
                print(f"WebDriver instance for {username} has been closed.")
            print("-" * 50)
            if i < len(accounts) - 1 : # If not the last account
                time.sleep(3) # Brief pause before starting the next account's browser

    print("\n--- Summary ---")
    print(f"Total accounts processed: {len(accounts)}")
    print(f"Successfully logged in: {overall_success_count}")
    print(f"Failed accounts: {len(failed_accounts)}")
    if failed_accounts:
        print("List of failed/skipped accounts:")
        for acc in failed_accounts:
            print(f"  - {acc}")
    
    if len(failed_accounts) > 0:
        print("\nATTENTION: One or more logins failed or a critical error occurred.")
        # exit(1) # Uncomment to make GitHub Action fail if any account fails
    else:
        print("\nAll account login attempts processed successfully.")

if __name__ == "__main__":
    main()
