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

# --- Precise Element Selectors ---
USERNAME_SELECTOR = (By.ID, "inputEmail")
PASSWORD_SELECTOR = (By.ID, "inputPassword")
LOGIN_BUTTON_SELECTOR = (By.ID, "login")

# --- Success Indicators (after login click) ---
SUCCESS_URL_CONTAINS = "clientarea.php"
SUCCESS_TITLE_CONTAINS = "Client Area" # General title check
SUCCESS_DASHBOARD_ELEMENT_SELECTOR = (By.XPATH, "//h1[normalize-space()='Dashboard']") # Primary success element

# New specific success message to look for after dashboard is confirmed
SUCCESS_MESSAGE_TEXT = "Log into your Client Area at least once every 45 days to prevent the deletion of your Free Service Plan."
# This XPath will find any element on the page containing the exact success message text.
# It's more robust to wrap it in normalize-space if there could be odd whitespace.
SUCCESS_MESSAGE_SELECTOR = (By.XPATH, f"//*[contains(normalize-space(.), '{SUCCESS_MESSAGE_TEXT}')]")


# --- Failure Indicator (after login click) ---
FAILURE_ELEMENT_SELECTOR = (By.XPATH, "//div[contains(@class, 'alert-danger') and normalize-space()='Login Details Incorrect. Please try again.']")


def setup_driver():
    """配置并返回一个全新的 Selenium WebDriver 实例"""
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
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
        WebDriverWait(driver, 25).until(EC.visibility_of_element_located(USERNAME_SELECTOR))
        
        print(f"Page title: '{driver.title}', URL: {driver.current_url}")

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
                EC.url_contains(SUCCESS_URL_CONTAINS), # Check URL first as it's a strong indicator
                EC.visibility_of_element_located(FAILURE_ELEMENT_SELECTOR) # Or failure message
            )
        )

        # Primary checks for login success or explicit failure message
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
            pass # Good, no failure message

        # Now check primary success conditions (Dashboard and URL/Title)
        if SUCCESS_URL_CONTAINS not in current_url or SUCCESS_TITLE_CONTAINS not in current_title:
            print(f"Login may have failed for {username}. URL or Title mismatch.")
            print(f"  URL: {current_url} (Expected part: '{SUCCESS_URL_CONTAINS}')")
            print(f"  Title: {current_title} (Expected part: '{SUCCESS_TITLE_CONTAINS}')")
            # If dashboard isn't visible either, it's a stronger failure sign
            try:
                if not driver.find_element(*SUCCESS_DASHBOARD_ELEMENT_SELECTOR).is_displayed():
                     print("  Dashboard header also not found. Marking as unclear/failed.")
                     save_debug_info(driver, username, "login_unclear_no_dash_url_title")
                     return False
            except NoSuchElementException:
                print("  Dashboard header not found. Marking as unclear/failed.")
                save_debug_info(driver, username, "login_unclear_no_dash_url_title")
                return False
        
        # Check for Dashboard H1 (primary content indicator of being in client area)
        try:
            dashboard_header = WebDriverWait(driver,10).until(
                EC.visibility_of_element_located(SUCCESS_DASHBOARD_ELEMENT_SELECTOR)
            )
            if dashboard_header.is_displayed():
                dashboard_visible = True
                dashboard_header_text = dashboard_header.text
                print(f"Dashboard header ('{dashboard_header_text}') is visible.")
            else: # Should not happen if visibility_of_element_located passed
                print("Dashboard header located but not visible (unexpected).")
        except TimeoutException:
            print("Dashboard header not found or not visible within timeout.")
            save_debug_info(driver, username, "login_no_dashboard_header")
            return False # If dashboard isn't there, it's not a full success

        # If dashboard is visible, now look for the SPECIFIC success message
        if dashboard_visible:
            print(f"Checking for specific success message: '{SUCCESS_MESSAGE_TEXT}'")
            try:
                specific_message_element = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(SUCCESS_MESSAGE_SELECTOR)
                )
                if specific_message_element.is_displayed():
                    found_specific_success_message = True
                    print(f"Found specific success message: '{specific_message_element.text.strip()}'")
                else:
                    print("Specific success message located but not visible.")
            except TimeoutException:
                print("Specific success message NOT found on the page.")
                # Depending on strictness, you might return False here if this message is mandatory.
                # For now, we'll log it and proceed if other conditions are met,
                # but flag overall success based on this.

        # Final success determination
        if dashboard_visible and found_specific_success_message:
            print(f"ALL SUCCESS CONDITIONS MET for {username}.")
            print(f"  URL: {current_url}, Title: {current_title}")
            print(f"  Dashboard: '{dashboard_header_text}', Specific Message: Found.")
            print("Pausing for 3 seconds as requested...")
            time.sleep(3)
            return True
        else:
            print(f"Login for {username} - primary conditions met but specific message MISSING or dashboard issue.")
            print(f"  Dashboard Visible: {dashboard_visible}, Specific Message Found: {found_specific_success_message}")
            save_debug_info(driver, username, "login_incomplete_final_check")
            return False

    except TimeoutException as te:
        print(f"A TimeoutException occurred for {username}: {str(te).splitlines()[0]}")
        save_debug_info(driver, username, "login_timeout_main")
    except Exception as e: # Catch-all for other Selenium or unexpected errors
        print(f"An unexpected error occurred for {username}: {type(e).__name__} - {str(e)}")
        save_debug_info(driver, username, f"login_unexpected_err_{type(e).__name__}")
    return False

def main():
    # Random delay: Sleep for a random number of seconds between 0 and 59 minutes (3540 seconds)
    # This happens if the cron job triggers at HH:00.
    random_delay_seconds = random.randint(0, 59 * 60)
    print(f"Script started. Will sleep for {random_delay_seconds // 60} minutes and {random_delay_seconds % 60} seconds before proceeding.")
    time.sleep(random_delay_seconds)
    print("Sleep finished. Starting account processing.")

    accounts_json_str = os.environ.get("ACCOUNTS_JSON")
    # ... (rest of the main function remains largely the same as the previous version) ...
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
    failed_accounts_details = [] # Store tuples of (username, reason)

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
            current_driver = setup_driver()
            if not current_driver:
                 msg = f"Failed to setup WebDriver for account {username}. Skipping."
                 print(msg)
                 failed_accounts_details.append((username, "WebDriver setup failed"))
                 continue
            
            login_successful_flag = login_single_account(current_driver, username, password)
            
            if login_successful_flag:
                overall_success_count += 1
                print(f"Successfully processed and verified account: {username}")
            else:
                # login_single_account should have printed the reason for failure.
                # We'll add a generic failure reason if not already more specific.
                failed_accounts_details.append((username, "Login or verification steps failed"))
                print(f"Failed to fully process/verify account: {username}")

        except Exception as e_outer:
            error_msg = f"A critical error occurred while processing account {username}: {type(e_outer).__name__} - {str(e_outer)}"
            print(error_msg)
            failed_accounts_details.append((username, f"Critical error: {type(e_outer).__name__}"))
            if current_driver:
                save_debug_info(current_driver, username, "account_loop_critical_err")
        finally:
            if current_driver:
                current_driver.quit()
                print(f"WebDriver instance for {username} has been closed.")
            print("-" * 50)
            # Small delay between browser instances.
            if i < len(accounts) - 1 : time.sleep(random.randint(3,7))


    print("\n--- Summary ---")
    print(f"Total accounts attempted: {len(accounts)}")
    print(f"Successfully logged in and verified: {overall_success_count}")
    failed_count = len(accounts) - overall_success_count
    print(f"Failed/Skipped accounts: {failed_count}")
    if failed_accounts_details:
        print("Details of failed/skipped accounts:")
        for acc_user, reason in failed_accounts_details:
            # Check if this username already exists in a more detailed report from login_single_account (less direct)
            # This summary is high level. Detailed logs are key.
            print(f"  - User: {acc_user}, Status: {reason}")
    
    if failed_count > 0:
        print("\nATTENTION: One or more logins failed or encountered a critical error.")
        # To make GitHub Action step fail if any account fails:
        # exit(1) 
    else:
        print("\nAll account login attempts processed and verified successfully.")


if __name__ == "__main__":
    main()
