from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import configparser
import os
from datetime import datetime
import pytz  # Add this import for timezone support



class CourtBooker:
    def __init__(self, headless=False, suppress_console=False, take_screenshots=False, use_config_date=False):
        """
        Initialize the court booking system
        
        Args:
            headless (bool): Run Chrome in headless mode if True
            suppress_console (bool): Suppress console output if True
            take_screenshots (bool): Whether to capture screenshots during the process
            use_config_date (bool): Use date from config rather than 6-day future date
        """
        # Set up logging with different levels for file and console
        self.logger = self._setup_logging(suppress_console)
        self.use_config_date = use_config_date
        self.config = self._load_config()
        self.logged_in = False
        self.take_screenshots = take_screenshots
        
        # Create screenshots directory if needed and screenshots are enabled
        self.screenshots_dir = "screenshots"
        if self.take_screenshots:
            os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Set up Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--start-maximized")
        
        # Suppress Chrome browser logs
        if suppress_console:
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
            os.environ['WDM_LOG_LEVEL'] = '0'  # Suppress webdriver-manager logs
        
        # Set up the WebDriver
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
            raise
            
        self.wait = WebDriverWait(self.driver, 10)
    
    def _setup_logging(self, suppress_console=False):
        """
        Set up logging with different levels for file and console
        
        Args:
            suppress_console (bool): If True, set console logging level to ERROR
                                   If False, set console logging level to INFO
        """
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)
        
        # File handler - always logs everything at INFO level
        file_handler = logging.FileHandler("booking_log.log")
        file_handler.setLevel(logging.INFO)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
        
        # Console handler - level depends on suppress_console parameter
        console_handler = logging.StreamHandler()
        console_level = logging.ERROR if suppress_console else logging.INFO
        console_handler.setLevel(console_level)
        console_format = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        return logger
    
    def _load_config(self):
        """Load configuration from config.ini file with date override"""
        config = configparser.ConfigParser()
        
        try:
            # Check if config.ini exists
            if not os.path.exists("config.ini"):
                self.logger.error("config.ini file not found")
                raise FileNotFoundError("config.ini file not found")
            
            config.read("config.ini")
            
            # Verify required sections and options exist
            required_sections = {
                'LOGIN': ['url', 'username', 'password'],
                'BOOKING': ['time', 'facility']  # Remove 'date' from required fields
            }
            
            for section, options in required_sections.items():
                if not config.has_section(section):
                    self.logger.error(f"Missing section '{section}' in config.ini")
                    raise ValueError(f"Missing section '{section}' in config.ini")
                
                for option in options:
                    if not config.has_option(section, option):
                        self.logger.error(f"Missing option '{option}' in section '{section}' in config.ini")
                        raise ValueError(f"Missing option '{option}' in section '{section}' in config.ini")
            
            # Override the date with a date 6 days in the future unless use_config_date is True
            if not self.use_config_date or not config.has_option('BOOKING', 'date'):
                # Set timezone to St. John's, Newfoundland (UTC-3:30)
                newfoundland_tz = pytz.timezone('America/St_Johns')
                current_date = datetime.now(newfoundland_tz)
                future_date = current_date + timedelta(days=6)
                future_date_str = future_date.strftime("%Y-%m-%d")
                
                # Create the 'date' option if it doesn't exist
                if not config.has_option('BOOKING', 'date'):
                    if not config.has_section('BOOKING'):
                        config.add_section('BOOKING')
                    config.set('BOOKING', 'date', future_date_str)
                # Override existing date
                else:
                    config.set('BOOKING', 'date', future_date_str)
                    
                self.logger.info(f"Date set to 6 days from now: {future_date_str}")
            
            self.logger.info("Configuration loaded successfully")
            return config
        
        except (configparser.Error, FileNotFoundError, ValueError) as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise


    def take_screenshot(self, name):
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.screenshots_dir}/{name}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            self.logger.info(f"Screenshot saved: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {str(e)}")
            return None
    
    def login(self):
        """Login to the booking website"""
        try:
            url = self.config['LOGIN']['url']
            username = self.config['LOGIN']['username']
            password = self.config['LOGIN']['password']
            
            self.logger.info(f"Navigating to {url}")
            self.driver.get(url)
            

            
            # Wait for login form to load and find elements
            self.logger.info("Attempting to log in")
            
            # MyVSCloud specific login elements
            username_field = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@id='weblogin_username']"))
            )
            password_field = self.driver.find_element(By.XPATH, "//input[@id='weblogin_password']")
            login_button = self.driver.find_element(By.XPATH, "//button[@id='weblogin_buttonlogin']")
            
            # Enter credentials and login
            username_field.send_keys(username)
            password_field.send_keys(password)
            

            login_button.click()
            
            # Handle "Login Warning - Active Session Alert" if it appears
            try:
                # Use a shorter timeout for this check to avoid long waits if not present
                active_session_alert = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//h1[normalize-space()='Login Warning - Active Session Alert']"))
                )
                
                if (active_session_alert):
                    self.logger.info("Active Session Alert detected")
                    
                    
                    # Click the Continue button to proceed
                    continue_button = self.driver.find_element(By.XPATH, "//button[@id='loginresumesession_buttoncontinue']")
                    continue_button.click()
                    
                    self.logger.info("Clicked Continue button on Active Session Alert")
            except (TimeoutException, NoSuchElementException):
                # No alert found, continue with normal flow
                self.logger.info("No Active Session Alert detected, proceeding with login")
            
            # Wait for successful login - looking for the household button which appears after login
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//h2[normalize-space()='Field House Courts']"))
            )
            
            # Set logged_in flag to True
            self.logged_in = True
            
            # Take screenshot after successful login
            
            self.logger.info("Login successful")
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Login failed: {str(e)}")
           
            return False
    
    def logout(self):
        """Logout from the booking website"""
        try:
            if not self.logged_in:
                self.logger.info("No active session to log out from")
                return True
            
            self.logger.info("Attempting to log out")
           
            
            # First click on the user menu that contains the SVG icon and username
            try:
                # Try to find the user menu by class name
                user_menu = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'menuitem__title') and contains(., '#')]"))
                )
                self.logger.info("Found user menu by class and ID")
                user_menu.click()
                
                # Now click on the Logout option in the dropdown
                logout_option = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'menuitem__text') and text()='Logout']"))
                )
                self.logger.info("Found logout option")
               
                
                logout_option.click()
                
                # Wait for "Sign In / Register" to appear, confirming successful logout
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//span[@class='menuitem__text' and text()='Sign In / Register']"))
                )
                
             
                self.logger.info("Logout successful - 'Sign In / Register' text found")
                self.logged_in = False
                return True
                
            except (TimeoutException, NoSuchElementException) as e:
                self.logger.error(f"Could not find user menu: {str(e)}")
               
                
                # Try alternative approach - look for any logout link
                self.logger.info("Trying alternative logout approach")
                try:
                    # Direct approach - try to find any logout link on the page
                    logout_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Log Out') or contains(text(), 'Logout')]")
                    logout_link.click()
                    
                    # Wait for "Sign In / Register" to appear
                    self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//span[@class='menuitem__text' and text()='Sign In / Register']"))
                    )
                    
                  
                    self.logger.info("Direct logout successful - 'Sign In / Register' text found")
                    self.logged_in = False
                    return True
                except Exception as direct_e:
                    self.logger.error(f"Direct logout approach failed: {str(direct_e)}")
                   
                    
                    # Last resort - try to navigate to login page directly
                    try:
                        self.logger.info("Attempting to navigate to login page directly")
                        self.driver.get(self.config['LOGIN']['url'])
                        
                        
                        # Check for "Sign In / Register" presence
                        sign_in_element = self.driver.find_elements(By.XPATH, "//span[@class='menuitem__text' and text()='Sign In / Register']")
                        
                        if sign_in_element or "login" in self.driver.current_url.lower():
                          
                            self.logger.info("Forced logout by navigation successful")
                            self.logged_in = False
                            return True
                        else:
                            self.logger.error("Failed to force logout by navigation")
                          
                            return False
                    except Exception as nav_e:
                        self.logger.error(f"Navigation approach failed: {str(nav_e)}")
                        return False
                    
        except Exception as e:
            self.logger.error(f"Logout failed: {str(e)}")
           
            return False
    
    def navigate_to_booking_page(self):
        """Navigate to the booking page and clear any existing selections"""
        try:
            self.logger.info("Navigating to booking page")
            
            # Take screenshot before clicking
          
            
            # Wait for and click on the Field House Courts link
            # Using a more flexible XPath to find the link containing "Field House Courts"
            field_house_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'tile')]//h2[contains(text(), 'Field House Courts')]/ancestor::a"))
            )
            
            self.logger.info("Found Field House Courts link, clicking...")
            field_house_link.click()
            
            # Wait for the page to load - check if "Facility Search" text is present
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Facility Search')]"))
            )
            self.logger.info("'Facility Search' text found, booking page loaded successfully")
            
            # Check for and handle "Clear Selection" button
            try:
                # Short timeout to quickly check for the Clear Selection button without prolonged waiting
                clear_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'multiselectlist__clearbutton') and .//span[contains(text(), 'Clear Selection')]]"))
                )
                
                self.logger.info("Found 'Clear Selection' button, clicking to reset previous selections")
               
                clear_button.click()
                
                # Wait briefly for the clear operation to complete
                self.wait.until(lambda d: not d.find_elements(By.XPATH, "//div[contains(@class, 'multiselectlist__selectionlist--hasselections')]"))
                self.logger.info("Successfully cleared previous selections")
               
                
            except (TimeoutException, NoSuchElementException):
                # No Clear Selection button found - this is normal for a fresh session
                self.logger.info("No previous selections to clear")
            
            # Take screenshot after the page has loaded
      
            
            self.logger.info("Successfully navigated to booking page")
            return True
        
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Failed to navigate to booking page: {str(e)}")
         
            return False

  
    def select_date(self):
        """Select the desired booking date using the dropdown selectors"""
        try:
            desired_date = self.config['BOOKING']['date']
            self.logger.info(f"Selecting date: {desired_date}")
            
            # Take screenshot before date selection
        
            
            # Click on the datepicker button to open it
            date_picker_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'datepicker-button')]"))
            )
            self.logger.info("Found datepicker button, clicking...")
            date_picker_button.click()
            
            # Parse the desired date
            year, month, day = desired_date.split('-')
            month_int = int(month)
            year_int = int(year)
            day_int = int(day)
            
            # Get month name from month number
            month_names = ["January", "February", "March", "April", "May", "June", 
                        "July", "August", "September", "October", "November", "December"]
            target_month = month_names[month_int - 1]
            
            # Take screenshot of opened datepicker
          
            
            # Step 1: Select the month from dropdown
            self.logger.info(f"Selecting month: {target_month}")
            month_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@id, 'month_selection_button')]"))
            )
            month_dropdown.click()
            
            
            # Select the target month from the dropdown options based on the provided pattern
            month_option = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//li[@role='option']//span[contains(@class, 'listitem__text') and text()='{target_month}']"))
            )
            self.logger.info(f"Found month option: {target_month}")
            month_option.click()
            
            
            # Step 2: Select the day from dropdown
            self.logger.info(f"Selecting day: {day_int}")
            day_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@id, 'day_selection_button')]"))
            )
            day_dropdown.click()
            
            
            # Select the target day from the dropdown options based on the provided pattern
            day_option = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//li[@role='option']//span[contains(@class, 'listitem__text') and text()='{day_int}']"))
            )
            self.logger.info(f"Found day option: {day_int}")
            day_option.click()
            
            
            # Step 3: Select the year from dropdown
            self.logger.info(f"Selecting year: {year_int}")
            year_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@id, 'year_selection_button')]"))
            )
            year_dropdown.click()
            
            
            # Select the target year from the dropdown options based on the provided pattern
            year_option = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//li[@role='option']//span[contains(@class, 'listitem__text') and text()='{year_int}']"))
            )
            self.logger.info(f"Found year option: {year_int}")
            year_option.click()
            
            
            # Take screenshot after selecting all date components
      
            # Click Done button to confirm date selection using the correct XPath
            done_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'datepicker-button-primary') and contains(text(), 'Done')]"))
            )
            self.logger.info("Clicking Done button to confirm date selection")
            done_button.click()
            
            # Wait for the search button to be clickable after date selection
            search_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@id, 'frwebsearch_buttonsearch')]"))
            )
            
            # Take screenshot before clicking search
        
            # Click search button
            self.logger.info("Clicking Search button")
            search_button.click()
            
            # Wait for search results to load
            
      
            self.logger.info(f"Date {desired_date} selected successfully")
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Failed to select date: {str(e)}")
            return False
        
    def select_court_and_time(self):
        """Select a court and time slot based on the sport type in config file"""
        try:
            desired_time = self.config['BOOKING']['time']
            desired_date = self.config['BOOKING']['date']
            facility_type = self.config['BOOKING']['facility'].lower()  # e.g., "badminton"
            court_number = self.config['BOOKING'].get('court_number', '')  # Optional court number
            
            self.logger.info(f"Looking for {facility_type} court (preferred court #{court_number if court_number else 'any'})")
            
            # Parse the date to match the format shown in search results
            year, month, day = desired_date.split('-')
            month_int = int(month)
            day_int = int(day)
            
            # Get abbreviated month name for matching
            month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month_int - 1]
            
            # Improved time parsing - handle formats like "7:00pm" or "7pm" or "19:00"
            # First, strip any whitespace and convert to lowercase
            clean_time = desired_time.strip().lower()
            
            # Check for AM/PM indicators
            am_indicator = any(x in clean_time for x in ['am', 'a.m.', 'a.m'])
            pm_indicator = any(x in clean_time for x in ['pm', 'p.m.', 'p.m'])
            
            # Extract the numeric part (hours and possibly minutes)
            numeric_part = ''.join([c for c in clean_time if c.isdigit() or c == ':'])
            
            if ':' in numeric_part:
                # Handle format like "7:00"
                hour_str, minute_str = numeric_part.split(':')
                hour = int(hour_str)
                minute = int(minute_str) if minute_str else 0
            else:
                # Handle format like "7"
                hour = int(numeric_part) if numeric_part else 0
                minute = 0
            
            # Apply AM/PM logic
            if pm_indicator and hour < 12:
                hour += 12  # Convert to 24-hour format
            elif am_indicator and hour == 12:
                hour = 0  # 12 AM is 00:00 in 24-hour format
            elif not am_indicator and not pm_indicator:
                # No AM/PM specified, use reasonable defaults
                if hour < 12:
                    am_indicator = True
                else:
                    pm_indicator = True
            
            # Determine AM/PM for display
            am_pm = "am" if am_indicator or (hour < 12 and not pm_indicator) else "pm"
            
            self.logger.info(f"Parsed time: {hour}:{minute:02d} {am_pm}")
            
            # Calculate the next hour for the end time
            next_hour = (hour + 1) % 24
            next_am_pm = "am" if next_hour < 12 else "pm"
            
            # Convert to 12-hour format for display
            hour_12 = hour % 12
            if hour_12 == 0:
                hour_12 = 12
            next_hour_12 = next_hour % 12
            if next_hour_12 == 0:
                next_hour_12 = 12
                
            self.logger.info(f"Looking for time slot: {hour_12}:{minute:02d} {am_pm} - {next_hour_12}:{minute:02d} {next_am_pm}")
            
            # Format time strings for matching
            time_formats = [
                f"{hour_12}:00 {am_pm} - {next_hour_12}:00 {next_am_pm}",     # 7:00 am - 8:00 am
                f"{hour_12}:{minute:02d} {am_pm} - {next_hour_12}:{minute:02d} {next_am_pm}",  # with minutes
                f" {hour_12}:00 {am_pm} - {next_hour_12}:00 {next_am_pm}",    # With leading space
                f" {hour_12}:00 {am_pm} -  {next_hour_12}:00 {next_am_pm}",   # With multiple spaces
                f"{hour_12}:{minute:02d} {am_pm}",                            # Just start time
                f"{hour_12} {am_pm}",                                         # Just hour and am/pm
            ]
            
      
            # Wait for the search results to fully load - look for the dateblock
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "dateblock"))
            )
            time.sleep(1)  # Wait a bit longer to ensure all results are loaded
            
            # Find all result content divs
            result_contents = self.driver.find_elements(By.CLASS_NAME, "result-content")
            self.logger.info(f"Found {len(result_contents)} court options")
            
            # Dictionary to track potential matches with scores
            court_matches = {}
            
            # First pass - find all courts that match our sport type and have available slots
            for court_div in result_contents:
                try:
                    # Get court title and description
                    court_title = court_div.find_element(By.XPATH, ".//h2/span").text
                    
                    try:
                        court_description = court_div.find_element(By.XPATH, ".//div[contains(@class, 'result-header__description')]").text
                    except NoSuchElementException:
                        court_description = ""
                    
                    self.logger.info(f"Examining court: {court_title}")
                    
                    # Check if this court matches our facility type
                    court_text = (court_title + " " + court_description).lower()
                    score = 0
                    
                    # Score the court based on matching criteria
                    if facility_type in court_text:
                        score += 100  # Base score for facility match
                        
                        # Add score for exact court number match if specified
                        if court_number and f"{facility_type} {court_number}" in court_text:
                            score += 50
                        
                        # Further boost score for courts specifically mentioning Badminton/Pickleball
                        if "badminton" in facility_type and "badminton" in court_text:
                            score += 30
                        if "pickle" in facility_type and "pickle" in court_text:
                            score += 30
                    
                    # Only consider courts with some relevance score
                    if score > 0:
                        # Find available time slots
                        time_slots = court_div.find_elements(
                            By.XPATH, 
                            ".//a[contains(@class, 'button') and contains(@class, 'cart-button')]"
                        )
                        
                        # Look for available slots matching our time
                        available_slots = []
                        for slot in time_slots:
                            if "success" in slot.get_attribute("class"):
                                slot_text = slot.text.strip()
                                # Check if any of our time formats match this slot
                                for time_format in time_formats:
                                    if time_format.lower() in slot_text.lower():
                                        available_slots.append((slot, slot_text))
                                        break
                        
                        # If we have matching available slots, add to our candidates
                        if available_slots:
                            # Add bonus for having our exact time available
                            score += 50
                            court_matches[court_title] = {
                                'div': court_div,
                                'score': score,
                                'slots': available_slots
                            }
                            self.logger.info(f"Found candidate court: {court_title} (Score: {score}) with {len(available_slots)} matching slots")
                
                except NoSuchElementException as e:
                    self.logger.info(f"Error examining court: {str(e)}")
                    continue
            
            # If no courts matched or had available slots
            if not court_matches:
                self.logger.error(f"No {facility_type} courts found with available slots matching {hour_12}:{minute:02d} {am_pm}")
              
                return False
            
            # Sort courts by score (highest first)
            sorted_courts = sorted(court_matches.items(), key=lambda x: x[1]['score'], reverse=True)
            
            # Select the highest scoring court
            best_court_name, best_court = sorted_courts[0]
            self.logger.info(f"Selected best matching court: {best_court_name} (Score: {best_court['score']})")
            
            # Take the first available matching slot
            selected_slot, slot_time = best_court['slots'][0]
            
          
            # Click on the available time slot
            self.logger.info(f"Clicking on time slot: {slot_time}")
            selected_slot.click()
            
            
            
      
            # Look for additional confirmation buttons
            try:
                # Check for instant-overlay class which might indicate a popup
                if "instant-overlay" in selected_slot.get_attribute("class"):
                    # Wait for a dialog or form to appear
                    self.logger.info("Waiting for booking dialog to appear")
                    overlay_elements = self.wait.until(
                        EC.presence_of_element_located((By.CLASS_NAME, "instant-overlay-content"))
                    )
            
                    # Look for buttons like "Continue" or "Book Now"
                    continue_buttons = self.driver.find_elements(
                        By.XPATH,
                        "//button[contains(text(), 'Continue') or contains(text(), 'Book') or contains(text(), 'Add to Cart')]"
                    )
                    
                    if continue_buttons:
                        self.logger.info(f"Clicking '{continue_buttons[0].text}' button")
                        continue_buttons[0].click()
                
                # If we reach this point, the slot might have been added to cart directly
                self.logger.info("Checking if time slot was added to cart")
                cart_indicators = self.driver.find_elements(By.XPATH, "//a[contains(@class, 'wt-cart-button')]")
                if cart_indicators:
                    self.logger.info("Item appears to be added to cart")
                    
            except (TimeoutException, NoSuchElementException) as e:
                self.logger.info(f"No additional confirmation needed or error occurred: {str(e)}")
                
       
            
            self.logger.info(f"{best_court_name} at {slot_time} selected and added to cart successfully")
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.error(f"Failed to select court and time: {str(e)}")
            return False
    
    def confirm_booking(self):
        """Complete the booking process by confirming the reservation"""
        try:
            self.logger.info("Confirming booking")
            
            # First, look for the "Add To Cart" button
            try:
                add_to_cart_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'multiselectlist__addbutton') and .//span[contains(text(), 'Add To Cart')]]"))
                )
                self.logger.info("Found 'Add To Cart' button, clicking...")
                
                add_to_cart_button.click()
                
                # Verify the booking details are correct
                booking_header = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//h1[@id='processingprompts_header']"))
                )
                
                header_text = booking_header.text
                self.logger.info(f"Found booking header: {header_text}")
                
                # Extract key details from the header
                facility_type = self.config['BOOKING']['facility'].lower()
                desired_date = self.config['BOOKING']['date']
                desired_time = self.config['BOOKING']['time']
                
                # Parse the date to format MM/DD/YYYY
                year, month, day = desired_date.split('-')
                formatted_date = f"{month}/{day}/{year}"
                
                # Check if essential details are in the header text
                date_in_header = formatted_date in header_text
                facility_in_header = facility_type.lower() in header_text.lower()
                
                if date_in_header and facility_in_header:
                    self.logger.info("Booking details verified successfully")
                else:
                    self.logger.warning(f"Booking details mismatch! Expected date: {formatted_date}, facility: {facility_type}")
                    self.logger.warning(f"Header content: {header_text}")
                    # Continue anyway since we've already added to cart
                
            except (TimeoutException, NoSuchElementException) as e:
                self.logger.warning(f"Could not find 'Add To Cart' button or verify details: {str(e)}")

                # May already be added to cart, so continue with checkout process
            
            # Proceed to checkout
            try:
                # Fill in required form fields - cell number and booking reason
                try:
                    # Get information from config file
                    cell_number = self.config['BOOKING'].get('cell_number', '')
                    booking_reason = self.config['BOOKING'].get('booking_reason', '')
                    
                    self.logger.info("Filling in required checkout information")
                    
                    # Fill in cell number field
                    cell_field = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//input[@id='question150906610']"))
                    )
                    cell_field.clear()
                    cell_field.send_keys(cell_number)
                    self.logger.info(f"Entered cell number: {cell_number}")
                    
                    # Fill in reason field
                    reason_field = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//input[@id='question150906642']"))
                    )
                    reason_field.clear()
                    reason_field.send_keys(booking_reason)
                    self.logger.info(f"Entered booking reason: {booking_reason}")
             
                    
                except (TimeoutException, NoSuchElementException) as e:
                    self.logger.warning(f"Could not find or fill out form fields: {str(e)}")
              
                # Look for continue or next button to proceed after filling form
                continue_buttons = self.driver.find_elements(
                    By.XPATH, 
                    "//button[contains(text(), 'Continue') or contains(text(), 'Next')] | " + 
                    "//input[@value='Continue' or @value='Next']"
                )
                
                if continue_buttons:
                    self.logger.info(f"Clicking continue button: '{continue_buttons[0].get_attribute('value') or continue_buttons[0].text}'")
                    continue_buttons[0].click()
                    self.take_screenshot("checkout")
            
                
                    
            except (TimeoutException, NoSuchElementException) as e:
                self.logger.error(f"Failed to proceed with checkout: {str(e)}")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to confirm booking: {str(e)}")
            return False


    def book_court(self):
        """Execute the full court booking workflow"""
        try:
            if not self.login():
                return False
            
            if not self.navigate_to_booking_page():
                return False
                
            if not self.select_date():
                return False
                
            if not self.select_court_and_time():
                return False
                
            if not self.confirm_booking():
                return False
                
            self.logger.info("Court booked successfully!")
            return True
            
        except Exception as e:
            self.logger.error(f"Unexpected error during booking process: {str(e)}")
            return False
        finally:
            # Always attempt to logout if we're logged in
            if self.logged_in:
                try:
                    self.logout()
                except Exception as e:
                    self.logger.error(f"Error during logout: {str(e)}")
            self.logger.info("Closing browser")
            self.driver.quit()

if __name__ == "__main__":
    # Parse command line arguments to make it configurable
    import argparse
    parser = argparse.ArgumentParser(description="Book a court automatically")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")
    parser.add_argument("--screenshots", action="store_true", help="Take screenshots (default: disabled)")
    parser.add_argument("--use-config-date", action="store_true", help="Use date from config file instead of 6 days from now")
    args = parser.parse_args()
    
    booker = CourtBooker(
        headless=args.headless,
        suppress_console=args.quiet,
        take_screenshots=args.screenshots,
        use_config_date=args.use_config_date
    )
    success = booker.book_court()
    
    # Exit with appropriate status code for automation scripts
    import sys
    sys.exit(0 if success else 1)