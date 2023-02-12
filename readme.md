# Pull USGA Golf Course Data
## Summary
This project was developed to be able to retrieve all data for US Golf courses from the [USGA website](ncrdb.usga.org).  No data is designed to be stored within the repository, this project allows the user to create the necessary files which can be used at the descretion of the user.

The capability to update the existing data also exists so that the user does not need to retrieve all data each time they want to check for updates.

## Software Requirements
Required dependencies:
- Python (3.10)
- beautifulsoup4==4.11.1
- lxml==4.9.2
- numpy==1.24.1
- pandas==1.5.3
- requests==2.28.2
- selenium==4.7.2

## Quick Start
Start by initializing the virtual environment.

```bash
>> pipenv install
>> pipenv shell
```

This project utilizes a Jupyter notebook as a workbook to run the necessary files and pull the data from source.  The Jupyter notebook requirements should automatically install when running the above commands.  Once installed, open the `get_data_workbook.ipynb` notebook in VSCode.  

Within the notebook press `Cmd + Shift + P` and select the PipEnv that is associated with this project.

In the second code cell, select the desired option.
- **option=1**: Either no data exists or partial data exists in the `data/` folder.  This option will webscrape the ncrdb.usga.org site which can take several hours to run.  If partial data exists, set the `existing_course_details = {dataframe with existing data}`.
- **option=2**: All data exists and will be read directly from csv files in the `data/` directory.

Courses should be available to access for analysis.
  
## Licensing and Acknowledgements
All data was retrieved from the [USGA Course Database website](ncrdb.usga.org) and is free to use.  Resale of this data is prohibited.