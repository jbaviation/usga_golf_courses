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
import os


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


def get_course_details(url, course_id):
    """Read the course tee details for the provided url.
    
    Parameters
    ----------
    url : str
        USGA NCRDB website url to pull tee data.
    
    Returns
    -------
    """

    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')

    # Get table
    tbl_id = 'gvTee'
    tee_table = soup.find(attrs={'id': tbl_id})

    # If no table exists
    if tee_table is None:
        return None

    # Initialize course deets and loop thru
    course_deets = []
    for i, tr in enumerate(tee_table.find_all('tr')):

        # Handle the header
        if i==0:
            header = [re.sub(r'[^A-Za-z0-9\._/]+', '', re.sub(r'\s+', '_', th.text.lower())).strip('_') for th in tr.find_all('th')]
            header += ['course_id']
            continue

        # Loop thru each column
        course_tee = [re.sub(r'[^A-Za-z0-9\./]+', '', td.text.lower()) for td in tr.find_all('td')] + [course_id]
            
        # apppend tee to course_deets
        course_deets.append(course_tee)

    # Create dataframe and clean
    df = pd.DataFrame(course_deets, columns=header).drop(['', 'ch'], axis=1)
    df.insert(0, 'course_id', df.pop('course_id'))
    
    return df


def get_course_details_all(courses, existing_data=None, update=False, sleep=1, progress_bar=True):
    """Loop thru all courses from get_courses() or restore_courses().

    Parameters
    ----------
    courses : pd.DataFrame
        Courses DataFrame which is a result of calling get_courses() or restore_courses().
    existing_data : pd.DataFrame, optional
        If a partial list or full list already exists, include it here. 
    update : bool, default=False
        TODO: False will ignore course ids that already exist.  True will look for changes to the existing courses.
    sleep : int
        Sleep time in between website hits.
    progress_bar : bool, default=True
        Whether or not to show the progress bar. True is recommended.

    Returns
    -------
    dict
        'all_courses' : DataFrame of all course details
        'new_courses' : DataFrame of only new course details
        'failed_courses' : DataFrame of courses that failed
        'modified_courses' : DataFrame of courses that have modified data
        'skipped_courses' : DataFrame of courses that were skipped not out of error
    """

    # Get list of existing course_ids from existing_data
    exclude_course_ids = []
    if existing_data is not None:
        exclude_course_ids = existing_data['course_id'].unique().tolist()
    
    # Loop thru courses to get course details
    names = ['all_courses', 'new_courses', 'failed_courses', 'modified_courses', 'skipped_courses']
    all_courses = []
    new_courses = []
    failed_courses = []
    modified_courses = []
    skipped_courses = []
    for i, row in courses.iterrows():
        # Print status
        if progress_bar:
            printProgressBar(i, len(courses), prefix=f"Processing {row['course_id']}")

        # Check if this course is in exclude_course_ids
        if row['course_id'] in exclude_course_ids:
            skipped_courses.append(row)
            all_courses.append(existing_data[existing_data['course_id']==row['course_id']])
            continue

        # Get course details
        try:
            tees = get_course_details(row['url'], row['course_id'])
        except:
            failed_courses.append(row)
            continue

        # Append data
        if tees is None:
            skipped_courses.append(row)
        # TODO: add check for modified courses
        else:
            all_courses.append(tees)
            new_courses.append(tees)

        # Wait between hits
        time.sleep(sleep)

    # Finalize progress bar
    if progress_bar:
        printProgressBar(len(courses), len(courses), prefix=f"COMPLETED")

    # Once done iterating convert all dataframe lists into dataframes
    out_dict = {}
    for ls, name in zip([all_courses, new_courses, failed_courses, modified_courses, skipped_courses], names):
        if len(ls) == 0:
            out_dict[name] = None
        else:
            out_dict[name] = pd.concat(ls).reset_index(drop=True)

    return out_dict


def clean_courses(courses):
    """Clean the DataFrame returned from get_courses() or restore_courses()."""
    df = courses.copy()

    # Utilize title case structure
    for col in ['club_name', 'course_name', 'city']:
        df[col] = df[col].str.title()

    return df


def store_course_details(dfs, data_folder='data'):
    """Store the get_course_details_all()['all_courses'] dataframe as a csv.

    Parameters
    ----------
    dfs : dict
        Dictionary containing DataFrames under the following keys:
        'all_courses' : DataFrame of all course details
        'new_courses' : DataFrame of only new course details
        'failed_courses' : DataFrame of courses that failed
        'modified_courses' : DataFrame of courses that have modified data
        'skipped_courses' : DataFrame of courses that were skipped not out of error
    data_folder : str
        Directory that the data is to be stored in.
    """
    # Rewrite to make each dataframe a file
    filenames = [os.path.join(data_folder, f'all_course_details_{get_date()}.csv'),
                 os.path.join(data_folder, f'new_course_details_{get_date()}.csv'),
                 os.path.join(data_folder, f'failed_course_details_{get_date()}.csv'),
                 os.path.join(data_folder, f'modified_course_details_{get_date()}.csv'),
                 os.path.join(data_folder, f'skipped_course_details_{get_date()}.csv')]

    keys = ['all_courses', 'new_courses', 'failed_courses', 'modified_courses', 'skipped_courses']

    for key, filename in zip(keys, filenames):
        df = dfs[key]

        # If none, write an empty file
        if df is None:
            with open(filename, 'w+') as f:
                f.write('')
        else:
            df.to_csv(filename, index=False)

        print(f'INFO: Successfully wrote the course details dataframe to {filename}')


def restore_course_details(data=None, dates=None, data_folder='data'):
    """Restore the get_course_details_all() dataframe from csv.

    Parameters
    ----------
    data : list of {'all_courses', 'new_courses', 'failed_courses', 'modified_courses', 'skipped_courses'}, optional
        Desired data to be returned.  Defaults to all files.
    dates : str or datetime or list of, optional
        Date of files that are being restored. If list is used, it must be the same length as data. If all files
        contain the same date, a str or datetime can be entered. If no date is entered, today's date is assumed
        for all files.
    data_folder : str, default='data'
        Directory that the data is to be stored in.

    Returns
    -------
    dict
        Dictionary containing DataFrames under the selected keys of the following:
        'all_courses' : DataFrame of all course details
        'new_courses' : DataFrame of only new course details
        'failed_courses' : DataFrame of courses that failed
        'modified_courses' : DataFrame of courses that have modified data
        'skipped_courses' : DataFrame of courses that were skipped not out of error
    """
    # Create file_mapping
    fmap = {'all_courses': 'all_course_details_{}.csv', 
            'new_courses': 'new_course_details_{}.csv', 
            'failed_courses': 'failed_course_details_{}.csv', 
            'modified_courses': 'modified_course_details_{}.csv', 
            'skipped_courses': 'skipped_course_details_{}.csv'}

    # Make data a list
    if data is None:
        data = list(fmap.keys())
    elif isinstance(data, str):
        data = [data]
    elif not isinstance(data, list):
        raise TypeError(f'data is of type {type(data)}.  Must be either str or list.')
    elif any([d not in fmap.keys() for d in data]):
        raise IndexError(f'Items in data must be in {list(fmap.keys())}')

    # Make sense of dates
    if dates is None:
        dates = [get_date() for _ in range(len(data))]
    elif isinstance(dates, str):
        dates = [pd.to_datetime(dates).strftime('%Y%m%d') for _ in range(len(data))]
    elif isinstance(dates, (list, tuple)) & (len(dates)==len(data)):
        dates = [pd.to_datetime(d).strftime('%Y%m%d') for d in dates]
    else:
        raise LookupError('Unable to match up date input with data')

    # Read files
    dfs = {}
    for key, date in zip(data, dates):
        filename = os.path.join(data_folder, fmap[key].format(date))
        try:
            df = pd.read_csv(filename)
        except:
            df = None
        dfs[key] = df

    return dfs


# Store the dataframe
def store_courses(df, data_folder='data'):
    """Store the get_courses() dataframe as a csv.

    Parameters
    ----------
    df : pd.DataFrame
        Course DataFrame to be saved.
    data_folder : str
        Directory that the data is to be stored in.
    """
    # Set filename
    file = os.path.join(data_folder, f'courses_{get_date()}.csv')

    df.to_csv(file, index=False)
    print(f'INFO: Successfully wrote the courses dataframe to {file}')


def restore_courses(date=None, data_folder='data'):
    """Restore get_courses() dataframe from the csv.
    
    Parameters
    ----------
    date : str or datetime, optional
        Date of the stored courses file.
    data_folder : str, optional
        Directory that the data is to be retrieved from. No input assumes today's date.

    Returns
    -------
    pd.DataFrame
        Containing all courses retrieved from the get_courses() function.
    """

    # Set filename
    filename = os.path.join(data_folder, f'courses_{get_date(date)}.csv')
    return pd.read_csv(filename)


def get_date(date=None):
    """Get date mostly used in naming files.
    
    Parameters
    ----------
    date : str or datetime, optional
        Date to return as string.  No input returns today's date

    Returns
    -------
    str
        Date in YYYYMMDD format.
    """

    fmt = '%Y%m%d'
    if date is None:
        return datetime.datetime.now().strftime(fmt)
    else:
        return pd.to_datetime(date).strftime('%Y%m%d')


def printProgressBar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

