import os
import json
import time
import random # For random sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException

LOGIN_URL = "https://client.webhostmost.com/login"
EXPECTED_LOGIN_PAGE_TITLE = "Log In To Client Area - Web Host Most" # Exact title for login page

# --- Precise Element Selectors ---
USERNAME_SELECTOR = (By.ID, "inputEmail")
PASSWORD_SELECTOR = (By.ID, "inputPassword")
LOGIN_BUTTON_SELECTOR = (By.ID, "login")

# --- Success Indicators (after login click) ---
SUCCESS_URL_CONTAINS = "clientarea.php"
EXPECTED_CLIENT_AREA_TITLE = "Client Area - Web Host Most" # Exact title for successful login
SUCCESS_DASHBOARD_ELEMENT_SELECTOR = (By.XPATH, "//h1[normalize-space()='Dashboard']")

SUCCESS_MESSAGE_TEXT = "Log into your Client Area at least once every 45 days to prevent the deletion of your Free Service Plan."
SUCCESS_MESSAGE_SELECTOR = (By.XPATH, f"//*[contains(normalize-space(.), '{SUCCESS_MESSAGE_TEXT}')]")

# --- Failure Indicator (after login click) ---
FAILURE_ELEMENT_SELECTOR = (By.XPATH, "//div[contains(@class, 'alert-danger') and normalize-space()='Login Details Incorrect. Please try again.']")


def setup_driver():
    """配置并返回一个全新的 Selenium WebDriver 实例"""
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito") # Explicit incognito mode
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    new_driver = None
    try:
        print("Setting up new WebDriver instance...")
        # Forcing re-download of driver can be done by clearing webdriver-manager cache if needed
        # but usually ChromeDriverManager().install() handles versioning well.
        service = ChromeService(ChromeDriverManager().install())
        new_driver = webdriver.Chrome(service=service, options=options)
        print("New WebDriver instance setup successfully.")
    except Exception as e:
        print(f"Critical Error: Could not initialize Chrome WebDriver: {e}")
        raise
    
    if new_driver:
        new_driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return new_driver

def save_debug_info(driver, username, stage="error"):
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
    print(f"Attempting to log in as {username} using current browser session...")
    try:
        print(f"Navigating to login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # Wait for login page to be ready and check title
        WebDriverWait(driver, 25).until(EC.visibility_of_element_located(USERNAME_SELECTOR))
        if driver.title != EXPECTED_LOGIN_PAGE_TITLE:
            print(f"Warning: Login page title mismatch. Expected '{EXPECTED_LOGIN_PAGE_TITLE}', got '{driver.title}'")
            # Potentially save_debug_info here if this is critical, but proceed for now
        else:
            print(f"Login page title confirmed: '{driver.title}'")

        print(f"URL after load: {driver.current_url}")

        username_field = driver.find_element(*USERNAME_SELECTOR)
        username_field.clear()
        username_field.send_keys(username)
        print("Username entered.")

        password_field = driver.find_element(*PASSWORD_SELECTOR)
        password_field.clear()
        password_field.send_keys(password)
        print("Password entered.")
        
        print(f"Attempting to click login button (ID: {LOGIN_BUTTON_SELECTOR[1]})")
        try:
            login_button = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR))
            print("Login button clickable. Executing click via JS.")
            driver.execute_script("arguments[0].click();", login_button)
        except TimeoutException:
            print(f"Login button (ID: {LOGIN_BUTTON_SELECTOR[1]}) not 'clickable'. Saving debug info.")
            save_debug_info(driver, username, "login_btn_unclickable")
            return False
        except (NoSuchElementException, ElementNotInteractableException) as e_click:
            print(f"Could not find/interact with login button: {e_click}")
            save_debug_info(driver, username, "login_btn_interact_fail")
            return False
        
        print("Login click attempted. Waiting for page transition or failure message (30s timeout)...")
        WebDriverWait(driver, 30).until(
            EC.any_of(
                EC.url_contains(SUCCESS_URL_CONTAINS), # URL is a strong indicator
                EC.title_is(EXPECTED_CLIENT_AREA_TITLE), # Exact title match
                EC.visibility_of_element_located(FAILURE_ELEMENT_SELECTOR)
            )
        )

        current_url = driver.current_url
        current_title = driver.title
        dashboard_visible = False
        dashboard_header_text = "Not checked/found"
        found_specific_success_message = False

        try: # Check failure message first
            failure_element = driver.find_element(*FAILURE_ELEMENT_SELECTOR)
            if failure_element.is_displayed():
                print(f"Login failed for {username}. Found failure indicator: '{failure_element.text}'")
                save_debug_info(driver, username, "login_fail_message")
                return False
        except NoSuchElementException:
            pass 

        # --- Primary Success Condition Checks ---
        # 1. URL
        url_ok = SUCCESS_URL_CONTAINS in current_url
        if not url_ok:
            print(f"  URL mismatch: Got '{current_url}', expected to contain '{SUCCESS_URL_CONTAINS}'")

        # 2. Exact Page Title for Client Area
        title_ok = current_title == EXPECTED_CLIENT_AREA_TITLE
        if not title_ok:
            print(f"  Title mismatch: Got '{current_title}', expected '{EXPECTED_CLIENT_AREA_TITLE}'")

        # 3. Dashboard H1 element
        try:
            dashboard_header = WebDriverWait(driver,10).until(
                EC.visibility_of_element_located(SUCCESS_DASHBOARD_ELEMENT_SELECTOR)
            )
            if dashboard_header.is_displayed():
                dashboard_visible = True
                dashboard_header_text = dashboard_header.text
                print(f"  Dashboard header ('{dashboard_header_text}') is visible.")
        except TimeoutException:
            print("  Dashboard header not found or not visible within timeout.")
        
        # 4. Specific success message text (if other primary conditions met)
        if url_ok and title_ok and dashboard_visible:
            print(f"  Checking for specific success message: '{SUCCESS_MESSAGE_TEXT}'")
            try:
                specific_message_element = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(SUCCESS_MESSAGE_SELECTOR)
                )
                if specific_message_element.is_displayed():
                    found_specific_success_message = True
                    print(f"  Found specific success message: '{specific_message_element.text.strip()}'")
            except TimeoutException:
                print("  Specific success message NOT found on the page.")
        
        # --- Final Success Determination ---
        if url_ok and title_ok and dashboard_visible and found_specific_success_message:
            print(f"ALL SUCCESS CONDITIONS MET for {username}.")
            print(f"  URL: {current_url}, Title: {current_title}")
            print(f"  Dashboard: '{dashboard_header_text}', Specific Message: Found.")
            print("Pausing for 2 seconds as requested...")
            time.sleep(2) # Pause for 2 seconds after all checks pass
            return True
        else:
            print(f"Login for {username} FAILED or some success conditions not met.")
            print(f"  Status: URL_OK={url_ok}, TITLE_OK={title_ok}, DASHBOARD_VISIBLE={dashboard_visible}, SPECIFIC_MESSAGE_FOUND={found_specific_success_message}")
            save_debug_info(driver, username, "login_incomplete_final_check")
            return False

    except TimeoutException as te:
        print(f"A TimeoutException occurred for {username}: {str(te).splitlines()[0]}")
        save_debug_info(driver, username, "login_timeout_main")
    except Exception as e:
        print(f"An unexpected error occurred for {username}: {type(e).__name__} - {str(e)}")
        save_debug_info(driver, username, f"login_unexpected_err_{type(e).__name__}")
    return False

def main():
    random_delay_seconds = random.randint(0, 59 * 60)
    print(f"Script started. Will sleep for {random_delay_seconds // 60} minutes and {random_delay_seconds % 60} seconds before proceeding.")
    time.sleep(random_delay_seconds)
    print("Sleep finished. Starting account processing.")

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
    failed_accounts_details = [] 

    for i, account in enumerate(accounts):
        username = account.get("username")
        password = account.get("password")
        
        print(f"\n--- Processing Account {i+1} of {len(accounts)}: {username} ---")

        if not username or not password:
            msg = f"Skipping account {username or 'N/A'} due to missing credentials."
            print(f"Warning: {msg}")
            failed_accounts_details.append((username or "N/A", "Missing credentials"))
            continue
        
        current_driver = None
        login_successful_flag = False
        try:
            current_driver = setup_driver() # New, clean browser instance
            if not current_driver:
                 msg = f"Failed to setup WebDriver for account {username}. Skipping."
                 print(msg)
                 failed_accounts_details.append((username, "WebDriver setup failed"))
                 continue
            
            # Redundant if setup_driver ensures incognito/fresh profile, but can be added if paranoid:
            # print("Explicitly deleting all cookies for the new driver session (belt-and-suspenders).")
            # current_driver.delete_all_cookies()

            login_successful_flag = login_single_account(current_driver, username, password)
            
            if login_successful_flag:
                overall_success_count += 1
                print(f"Successfully processed and verified account: {username}")
            else:
                failed_accounts_details.append((username, "Login or verification steps failed (see logs above)"))
                print(f"Failed to fully process/verify account: {username}")

        except Exception as e_outer:
            error_msg = f"A critical error occurred while processing account {username}: {type(e_outer).__name__} - {str(e_outer)}"
            print(error_msg)
            failed_accounts_details.append((username, f"Critical error: {type(e_outer).__name__}"))
            if current_driver: # Save debug info if driver exists but error happened outside login_single_account
                save_debug_info(current_driver, username, "account_loop_critical_err")
        finally:
            if current_driver:
                current_driver.quit() # Close this account's browser instance
                print(f"WebDriver instance for {username} has been closed. Next account will get a new one.")
            print("-" * 50)
            if i < len(accounts) - 1 : time.sleep(random.randint(3,7)) # Small random pause between accounts

    print("\n--- Summary ---")
    print(f"Total accounts attempted: {len(accounts)}")
    print(f"Successfully logged in and verified: {overall_success_count}")
    failed_count = len(accounts) - overall_success_count
    print(f"Failed/Skipped accounts: {failed_count}")
    if failed_accounts_details:
        print("Details of failed/skipped accounts:")
        for acc_user, reason in failed_accounts_details:
            print(f"  - User: {acc_user}, Status: {reason}")
    
    if failed_count > 0:
        print("\nATTENTION: One or more logins failed or encountered a critical error.")
        # To make GitHub Action step fail if any account fails:
        # exit(1) # Make sure to uncomment this in your actual script if you want the Action to fail
    else:
        print("\nAll account login attempts processed and verified successfully.")

if __name__ == "__main__":
    main()
