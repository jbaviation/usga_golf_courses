from bs4 import BeautifulSoup
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.service import Service
import re
import time
import datetime


def get_states(base_url='https://ncrdb.usga.org/', returns='state_name_only'):
    """Get all states and state-ids on the https://ncrdb.usga.org/ webpage.
	
	Parameters
	----------
	base_url : str, default='https://ncrdb.usga.org/'
		USGA NCRDB base url. This shouldn't change unless the host changes its base url.
    returns : {'state_name_only', 'state_name_and_id'}, default='state_name_only

	Returns
	-------
	list of (state_name, state_id) or state_name
		Depends on returns parameter to determine what is returned
    """

    page = requests.get(base_url)
    soup = BeautifulSoup(page.content, 'html.parser')

    state_list = []
    for opt in soup.find(attrs={'id': 'ddState'}).find_all('option'):
        if opt.text == '(Select)':
            continue
        
        if returns == 'state_name_only':
            state_list.append(opt.text)
        elif returns == 'state_name_and_id':
            state_list.append((opt.text, opt['value']))
        else:
            raise NameError(f'returns=[{returns}] which is not a valid name.')
        
    return state_list
            

def get_courses_by_state(state, archive=None, driver_loc='/opt/homebrew/bin/chromedriver', base_url='https://ncrdb.usga.org/'):
    """Get a DataFrame of all the courses in the provided state.  
    
    Parameters
    ----------
    state : str
        The State/Province that will the courses will be pulled from.  Be sure that the inputted state exists in the get_states()
        function.
    archive : pd.DataFrame, optional
        If this is an incremental pull, input the DataFrame from the last pull to see what the changes are.
    driver_loc : str, default='/opt/homebrew/bin/chromedriver'
        The local location of your Chrome Driver.  To find the location to but in this field enter the following command:
        >>> type chromedriver
        chromedriver is /opt/homebrew/bin/chromedriver
	base_url : str, default='https://ncrdb.usga.org/'
		USGA NCRDB base url. This shouldn't change unless the host changes its base url.

    Returns
    -------
    pd.DataFrame
        Containing all courses in the listed state or if archive is not None, returns the new and different course instances.
    """
    
    # Initiate webdriver
    s = Service(driver_loc)
    driver = webdriver.Chrome(service=s)
    driver.get(base_url)

    # Select state
    select = Select(driver.find_element('id', 'ddState'))
    select.select_by_visible_text(state)

    # Click submit button and wait for table
    driver.find_element('id', 'myButton').click()
    tbl_id = 'gvCourses'
    try:
        WebDriverWait(driver, 10).until(expected_conditions.visibility_of_element_located((By.ID, tbl_id)))
    except:
         driver.quit()
         return None

    # Get soup of current page
    new_soup = BeautifulSoup(driver.page_source, 'lxml')
    driver.quit()

    # Get table object
    courses_tbl = new_soup.find(attrs={'id': tbl_id})

    # Get headers
    headers = ['url', 'course_id', 'last_updated'] + [col.text for col in courses_tbl.find('thead').find_all('div')]
    headers = [re.sub(r'[^a-z0-9]+', '_', col.lower()) for col in headers]  # make headers sql-like

    if archive is not None:
        pass

    # Get all courses
    courses = []
    for tr in courses_tbl.find('tbody').find_all('tr'):
        # Initialize new course
        course = {}

        # Find link, course id in row
        try:
            url_ext = tr.find_all('a', href=True)[0]['href']
            course_id = re.search(r'CourseID=(\d+)', url_ext).groups()[0]

            course['url'] = base_url + url_ext
            course['course_id'] = course_id

        except:
            # If no url found, set to none
            course['url'] = None
            course['course_id'] = None

        # Loop thru each element of row
        for i, td in enumerate(tr.find_all('td')):
            course[headers[i+3]] = td.text  # offset by 3 to account for additional headers not in table

        # Set the updated time
        course['last_updated'] = datetime.datetime.now()

        # Check if in archive
        if archive is not None:
            # Create criteria for matching:
            #   url: checks if url is in the archive
            #   course_id: checks if course_id is in the archive
            #   city: if course_id is found, checks that city of that course_id matches archive

            criteria = {}
            criteria['url'] = archive['url'].eq(base_url + url_ext).any()  # see if url is in archive
            criteria['course_id'] = archive['course_id'].eq(course_id).any()  # see if course_id is in archive
            if criteria['course_id']:
                # See if city matches
                criteria['city'] = archive.loc[archive['course_id'].eq(course_id), 'city'].eq(course['city']).all()
            else:
                criteria['city'] = False

            # Determine what to do with the row data
            if all(criteria.values()):
                # If all criteria are True, this row can be skipped
                continue

            elif 0 < sum(criteria.values()) < len(criteria.values()):
                # If any are False, keep this row but WARN
                print(f'WARNING: CourseID {course_id} contains modified data.')
                courses.append(course)

            else:
                # If all are False, this is new data
                print(f'INFO: CourseID {course_id} is a new course.')
                courses.append(course)
        
        # No archive was provided
        else:
            # Append each course to the courses list
            courses.append(course)

    # Turn courses into DataFrame, and create course_id column to use as foreign key
    if len(courses) > 0:
        courses = pd.DataFrame(courses)
        courses['url'] = courses.pop('url')
        courses['last_updated'] = courses.pop('last_updated')
        return courses
    else:
        print('INFO: No new data is present, returning empty DataFrame.')
        return pd.DataFrame(columns=headers)


# Combine all courses in one DataFrame
def get_courses(states, archive=None, driver_loc='/opt/homebrew/bin/chromedriver', base_url='https://ncrdb.usga.org/'):
    """Get a DataFrame of all the courses in the provided states.  
    
    Parameters
    ----------
    state : list of str
        A list of the States/Provinces that the courses will be pulled from.  Be sure that the inputted state exists in the get_states()
        function.
    archive : pd.DataFrame, optional
        If this is an incremental pull, input the DataFrame from the last pull to see what the changes are.
    driver_loc : str, default='/opt/homebrew/bin/chromedriver'
        The local location of your Chrome Driver.  To find the location to but in this field enter the following command:
        >>> type chromedriver
        chromedriver is /opt/homebrew/bin/chromedriver
	base_url : str, default='https://ncrdb.usga.org/'
		USGA NCRDB base url. This shouldn't change unless the host changes its base url.

    Returns
    -------
    pd.DataFrame
        Containing all courses in the listed states or if archive is not None, returns the new and different course instances.
    """

    # Loop thru the states and combine dataframes
    course_list = []
    for state in states:
        # Pull data from the state
        courses = get_courses_by_state(state=state, 
                                       archive=archive,
                                       driver_loc=driver_loc,
                                       base_url=base_url)
        if courses is not None:
            course_list.append(courses)
        else:
            print(f'WARNING: {state} contains no courses.')

        # Wait between pulls
        time.sleep(3)

    # Return the concatenated dataframe
    return pd.concat(course_list)


# Store the dataframe
def store_courses(df, file='data/courses.csv'):
    """Store the get_courses() dataframe as a csv.

    Parameters
    ----------
    df : pd.DataFrame
        Course DataFrame to be saved.
    file : str
        Filename to store the data.
    """

    df.to_csv(file)
    print(f'INFO: Successfully wrote the courses dataframe to {file}')


def restore_courses(file='data/courses.csv'):
    """Restore get_courses() dataframe from the csv.
    
    Parameters
    ----------
    file : str
        Filename to store the data.

    Returns
    -------
    pd.DataFrame
        Containing all courses retrieved from the get_courses() function.
    """

    return pd.read_csv(file)



# Scrape data from each course and create new DataFrame with course_id as foreign key