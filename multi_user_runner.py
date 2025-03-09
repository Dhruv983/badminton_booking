import os
import sys
import logging
import configparser
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from court_booker import CourtBooker
import pytz

class MultiUserBooker:
    def __init__(self, config_path="config.ini", headless=True, suppress_console=False, take_screenshots=False, parallel=True, max_workers=None, use_config_date=False):
        self.config_path = config_path
        self.headless = headless
        self.suppress_console = suppress_console
        self.take_screenshots = take_screenshots
        self.parallel = parallel  # New parameter to control parallel execution
        self.max_workers = max_workers  # Number of parallel workers (None = auto-determine)
        self.use_config_date = use_config_date  # Whether to use date from config
        
        # Set up logging
        self.logger = self._setup_logging()
        
        # Create results directory
        self.results_dir = "results"
        os.makedirs(self.results_dir, exist_ok=True)

    def create_chrome_options(headless=True):
        chrome_options = webdriver.ChromeOptions()
        if headless:
            chrome_options.add_argument('--headless')
        
        # Required options for running in GitHub Actions
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--proxy-server="direct://"')
        chrome_options.add_argument('--proxy-bypass-list=*')
        chrome_options.add_argument('--start-maximized')
        
        return chrome_options
        
    def _setup_logging(self):
        """Set up multi-user booking logger"""
        logger = logging.getLogger("multi_user_booker")
        logger.setLevel(logging.INFO)
        
        # Clear handlers if any exist
        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler("multi_user_booking.log")
        file_handler.setLevel(logging.INFO)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        return logger
        
    def get_user_list(self):
        """Extract list of users from config file"""
        config = configparser.ConfigParser()
        config.read(self.config_path)
        
        users = []
        for section in config.sections():
            if section.endswith("_LOGIN"):
                user_id = section.replace("_LOGIN", "")
                users.append(user_id)
        
        return users

    def create_user_config(self, user_id):
        """Create a temporary config file for a specific user"""
        main_config = configparser.ConfigParser()
        main_config.read(self.config_path)
        
        # Create new config for this user
        user_config = configparser.ConfigParser()
        
        # Copy LOGIN section
        user_config['LOGIN'] = {}
        for key, value in main_config[f'{user_id}_LOGIN'].items():
            user_config['LOGIN'][key] = value
            
        # Copy BOOKING section
        user_config['BOOKING'] = {}
        for key, value in main_config[f'{user_id}_BOOKING'].items():
            user_config['BOOKING'][key] = value
            
        # Write to temporary file
        temp_config_path = f"temp_{user_id}_config.ini"
        with open(temp_config_path, 'w') as configfile:
            user_config.write(configfile)
            
        return temp_config_path

    def run_booking_for_user(self, user_id):
        """Run booking process for a specific user"""
        self.logger.info(f"Starting booking process for {user_id}")
        
        # Create user-specific config file
        temp_config_path = self.create_user_config(user_id)
        
        try:
            # Create a customized CourtBooker for this user
            booker = CustomCourtBooker(
                config_path=temp_config_path,
                user_id=user_id,
                headless=self.headless, 
                suppress_console=self.suppress_console,
                take_screenshots=self.take_screenshots,
                use_config_date=self.use_config_date
            )
            
            # Run the booking process
            success = booker.book_court()
            
            # Log result
            if success:
                self.logger.info(f"Booking successful for {user_id}")
            else:
                self.logger.error(f"Booking failed for {user_id}")
            
            # Save results to the results directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = os.path.join(self.results_dir, f"{user_id}_result_{timestamp}.txt")
            with open(result_file, 'w') as f:
                config = configparser.ConfigParser()
                config.read(temp_config_path)
                f.write(f"User: {user_id}\n")
                f.write(f"Time: {config['BOOKING']['time']}\n")
                f.write(f"Facility: {config['BOOKING']['facility']}\n")
                f.write(f"Status: {'Success' if success else 'Failed'}\n")
                f.write(f"Timestamp: {timestamp}\n")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during booking for {user_id}: {str(e)}")
            return False
            
        finally:
            # Clean up temporary config file
            try:
                os.remove(temp_config_path)
            except:
                pass

    def run_all_bookings(self):
        """Run booking process for all users"""
        self.logger.info("Starting multi-user booking process")
        
        users = self.get_user_list()
        self.logger.info(f"Found {len(users)} users to process")
        
        results = {}
        
        if self.parallel:
            # Parallel execution
            self.logger.info(f"Running bookings in parallel with {self.max_workers or 'auto'} workers")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_user = {
                    executor.submit(self.run_booking_for_user, user_id): user_id 
                    for user_id in users
                }
                
                # Process results as they complete
                for future in as_completed(future_to_user):
                    user_id = future_to_user[future]
                    try:
                        success = future.result()
                        results[user_id] = success
                    except Exception as e:
                        self.logger.error(f"Failed to process {user_id}: {str(e)}")
                        results[user_id] = False
        else:
            # Sequential execution (original implementation)
            for user_id in users:
                try:
                    # Add slight delay between users to avoid conflicts
                    if user_id != users[0]:
                        time.sleep(5)  # 5 second delay between users
                    
                    success = self.run_booking_for_user(user_id)
                    results[user_id] = success
                except Exception as e:
                    self.logger.error(f"Failed to process {user_id}: {str(e)}")
                    results[user_id] = False
        
        # Print summary
        self.logger.info("\n--- Booking Summary ---")
        for user_id, success in results.items():
            self.logger.info(f"{user_id}: {'SUCCESS' if success else 'FAILED'}")
        
        # Return overall success (True if all succeeded)
        return all(results.values())


class CustomCourtBooker(CourtBooker):
    def __init__(self, config_path=None, user_id=None, headless=False, suppress_console=False, 
                 take_screenshots=False, use_config_date=False):
        self.config_path = config_path
        self.user_id = user_id
        self.use_config_date = use_config_date
        
        # Create user-specific screenshot directory if screenshots are enabled
        if user_id and take_screenshots:
            self.screenshots_dir = f"screenshots_{user_id}"
            os.makedirs(self.screenshots_dir, exist_ok=True)
            
        super().__init__(headless=headless, suppress_console=suppress_console, 
                        take_screenshots=take_screenshots, use_config_date=use_config_date)
    
    def _load_config(self):
        """Override to use the custom config path with date override"""
        config = configparser.ConfigParser()
        
        try:
            # Use the specified config file path if provided
            if self.config_path and os.path.exists(self.config_path):
                config.read(self.config_path)
            else:
                # Fall back to default config.ini
                config.read("config.ini")
            
            # Verify required sections and options exist
            required_sections = {
                'LOGIN': ['url', 'username', 'password'],
                'BOOKING': ['time', 'facility']  # Remove 'date' from required fields
            }
            
            for section, options in required_sections.items():
                if not config.has_section(section):
                    self.logger.error(f"Missing section '{section}' in config file")
                    raise ValueError(f"Missing section '{section}' in config file")
                
                for option in options:
                    if not config.has_option(section, option):
                        self.logger.error(f"Missing option '{option}' in section '{section}' in config file")
                        raise ValueError(f"Missing option '{option}' in section '{section}' in config file")
            
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
                    
                self.logger.info(f"Date for {self.user_id} set to 6 days from now: {future_date_str}")
            
            self.logger.info(f"Configuration loaded successfully for {self.user_id if self.user_id else 'default user'}")
            return config
        
        except (configparser.Error, FileNotFoundError, ValueError) as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise
    
    def take_screenshot(self, name):
        """Override to save screenshots in user-specific directory"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.user_id:
                screenshot_name = f"{self.user_id}_{name}_{timestamp}.png"
            else:
                screenshot_name = f"{name}_{timestamp}.png"
                
            screenshot_path = os.path.join(self.screenshots_dir, screenshot_name)
            self.driver.save_screenshot(screenshot_path)
            self.logger.info(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {str(e)}")


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Run court booking for multiple users")
    parser.add_argument("--config", default="config.ini", help="Path to config file")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("--quiet", action="store_true", help="Suppress console messages")
    parser.add_argument("--screenshots", action="store_true", help="Take screenshots during execution")
    parser.add_argument("--sequential", action="store_true", help="Run bookings sequentially instead of in parallel")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: auto)")
    parser.add_argument("--use-config-date", action="store_true", help="Use date from config file instead of 6 days from now")
    args = parser.parse_args()
    
    # Set headless mode based on arguments (default is headless)
    headless = not args.visible if args.visible else args.headless
    
    # Run the multi-user booking process
    multi_booker = MultiUserBooker(
        config_path=args.config,
        headless=headless,
        suppress_console=args.quiet,
        take_screenshots=args.screenshots,
        parallel=not args.sequential,
        max_workers=args.workers,
        use_config_date=args.use_config_date
    )
    success = multi_booker.run_all_bookings()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)