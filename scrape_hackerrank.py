#!/usr/bin/env python
#
# File      : scrape_hackerrank.py
#
# Revision history:
#   Olaf Nielsen / 4.6.2019 / first version. Tested on Windows 10 with python 3.6 and 3.7
#
# Description:
'''
Extracts code submissions from www.hackerrank.com by scraping the site.

Uses python libraries selenium, BeautifulSoup, openpyxl.
Furthermore, selenium uses the chrome browser and it requires chromedriver.exe
(http://chromedriver.chromium.org/downloads)

Requires environment variables for hackerrank login : HACKERRANK_USER and HACKERRANK_PWD.

Output is written to an Excel file (scrape_hackerrank_<username>.xlsx')
'''
# -------------------------------------------------------------------------------------
import re, os, time, sys
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
import lxml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Color, colors, Border, Side
import pickle

# ------------------------------------------------------------------------------------
# writeToExcel
# -------------------------------------------------------------------------------------
def writeToExcel(submissions, filename) :
    """
    Writes submissions to an Excel file. Make sure the file is not already opened in Excel.
    """
    workBook = Workbook()
    excelSheet = workBook.active
    excelSheet.column_dimensions['A'].width = 35
    excelSheet.column_dimensions['B'].width = 13
    excelSheet.column_dimensions['C'].width = 10
    excelSheet.column_dimensions['D'].width = 6
    excelSheet.column_dimensions['E'].width = 10
    excelSheet.column_dimensions['F'].width = 150
    #                     
    excelSheet.append(['Challenge (link - in Excel click \'enable editing\' if not visible)', 'Time', 'Status', 'Points', 'Language', 'Code' ])
    for col in 'ABCDEF' :
        excelSheet[f'{col}1'].border = Border(top=Side(style='medium'), bottom=Side(style='medium'))
        excelSheet[f'{col}1'].alignment = Alignment(wrapText = True, vertical='center')
    #
    excelSheet.title = 'hackerrank submissions'  
    #
    currentRow = 2
    for challenge_text, value in sorted(submissions.items()):
        challenge_href, language, timesubmitted, status, points, code_href, code = value
        #
        # column A : link to the challenge
        txt = challenge_text.replace('"', "'")
        excelSheet.cell(row=currentRow, column=1, 
                        value=f'=HYPERLINK("{challenge_href}", "{txt}")')  
        excelSheet[f'A{currentRow}'].alignment = Alignment(vertical='top')
        excelSheet[f'A{currentRow}'].font = Font(bold=True, color=colors.DARKBLUE, underline='single')

        # column B : time submitted
        excelSheet.cell(row=currentRow, column=2, value=timesubmitted)
        excelSheet[f'B{currentRow}'].alignment = Alignment(vertical='top')
        # column C : status
        excelSheet.cell(row=currentRow, column=3, value=status)
        excelSheet[f'C{currentRow}'].alignment = Alignment(vertical='top')
        # column D : points
        excelSheet.cell(row=currentRow, column=4, value=points)
        excelSheet[f'D{currentRow}'].alignment = Alignment(vertical='top')
        # column E : language
        excelSheet.cell(row=currentRow, column=5, value=language)
        excelSheet[f'E{currentRow}'].alignment = Alignment(vertical='top')
        # column F : code submitted            
        excelSheet.cell(row=currentRow, column=6, value='\n'.join(code))    
        excelSheet[f'F{currentRow}'].alignment = Alignment(wrapText=True, vertical='top')
        excelSheet[f'F{currentRow}'].font = Font(bold=True, name='Courier New')
        excelSheet[f'F{currentRow}'].border = Border(left=Side(style='medium'), right=Side(style='medium'), 
                                                     top=Side(style='medium'), bottom=Side(style='medium'))
        #
        currentRow += 1
    workBook.save(filename) 
# end writeToExcel

# -------------------------------------------------------------------------------------
# find_indexLastPage
# -------------------------------------------------------------------------------------
def find_indexLastPage(driver):
    ''' returns number of submission pages. '''
    max_index = 0
    pagination = driver.find_elements_by_class_name('backbone')
    for element in pagination:
        index = element.get_attribute('data-attr8')
        if index : max_index = max(int(index), max_index)
    return max_index
# end find_indexLastPage

# -------------------------------------------------------------------------------------
# readCode
# -------------------------------------------------------------------------------------
def readCode(driver, url) :
    '''
    Reads the code block in a submission page 
    (e.g. https://www.hackerrank.com/challenges/repeated-string/problem)
    '''
    retry = True
    while retry :
        try :    
            print (f'opening page {url}')
            driver.get(url)
            time.sleep(5)
            # print (driver.page_source)
            codeBlock = driver.find_element_by_class_name('code-viewer') 
            # print ('codeBlock.text', codeBlock.text)
            driver.find_element_by_class_name('community-footer') # check if loading is complete
            retry = False
        except NoSuchElementException :
            print ('Retrying...')
    #
    code = []
    #print ('codeBlock.text', codeBlock.text)
    prevHasLineNumber = False     # two consecutive lines starting with number means a <cr>
    for line in codeBlock.text.split('\n') :
        hasLineNumber = re.search(r'^\d', line)
        if not hasLineNumber : code.append(line)
        elif prevHasLineNumber : code.append('')
        prevHasLineNumber = hasLineNumber
    return [code]
# end readCode

# -------------------------------------------------------------------------------------
# hackerrank_readSubmissions
# -------------------------------------------------------------------------------------
def hackerrank_readSubmissions(driver) :
    '''
    Determines all submissions. Then for each, reads the relevant code data.
    '''
    result = {}
    pageIndex = 1; lastPageIndex = 1
    # 
    while pageIndex <= lastPageIndex :
        url = 'https://www.hackerrank.com/submissions/all/page/' + str(pageIndex)
        print (f'opening page {url}')
        driver.get(url)
        # print (driver.page_source)
        # wait for the 'spinner' to complete. There must be a more elegant way to do this (google: invisibility_of_element_located)
        time.sleep(3)   
        try :
           submissions = driver.find_element_by_class_name('submissions_list')
           # print (submissions.get_attribute("innerHTML"))
           # check if loading is complete (exception raised, if not)
           driver.find_element_by_class_name('pagination-sub')   # this comes after the pagination block.
        except NoSuchElementException :
            print ('Retrying...')
            continue
        #
        if pageIndex == 1 : lastPageIndex = find_indexLastPage(driver)
        #
        # switch from selenium to beautifulsoup (easier to use, I think ...):
        soup = BeautifulSoup(submissions.get_attribute("innerHTML"), 'lxml')
        # print (soup.prettify())
        # 
        for submission in soup.find_all('div', class_='chronological-submissions-list-view') :
            challenge = submission.find('a', class_='challenge-slug')
            challenge_href = 'https://www.hackerrank.com' + challenge['href']+ '/problem'
            challenge_text = challenge.text
            language       = submission.find('div', class_='span2 submissions-language').p.text.strip() 
            timesubmitted  = submission.find('div', class_='span2 submissions-time').p.text.strip()
            status  = submission.find('div', class_='span3').p.text.strip()
            points  = submission.find('div', class_='span1').p.text.strip()
            code_button = submission.find('a', class_='btn')
            code_href = 'https://www.hackerrank.com/' + code_button['href']
            if challenge_text not in result:
                result[challenge_text] = [challenge_href, language, timesubmitted, status, points, code_href]
        # end for submission in ...
        pageIndex += 1
    # end while 
    return result
# end hackerrank_readSubmissions
 
# -------------------------------------------------------------------------------------
# hackerrank_login
# -------------------------------------------------------------------------------------
def hackerrank_login(driver, usr, pwd):
    driver.get('https://www.hackerrank.com/auth/login?h_l=body_middle_left_button&h_r=login')
    username = driver.find_element_by_name("username")
    password = driver.find_element_by_name("password")
    username.send_keys(usr)
    password.send_keys(pwd) 
    driver.find_element_by_xpath(\
        '/html/body/div[4]/div/div/div[3]/div[2]/div/div/div[2]/div/div/div[2]/div[1]/form/div[4]/button').click()
    time.sleep(3)
# end hackerrank_login

# -------------------------------------------------------------------------------------
# main
# -------------------------------------------------------------------------------------
def main():
    output_filename = 'hackerrank_submissions_' + os.getlogin() + '.xlsx'
    usr = os.getenv('HACKERRANK_USER')
    if not usr:
        print('Define env. var. with Hackerrank user name ($env:HACKERRANK_USER=....)')
        quit()
    pwd = os.getenv('HACKERRANK_PWD')
    if not pwd :
        print ('Define env. var. with Hackerrank password ($env:HACKERRANK_PWD=....)')
        quit()

    driver = webdriver.Chrome()  # could also use Firefox(), but Chrome starts faster.... 
    print (type(driver))
    try :
        hackerrank_login(driver, usr, pwd) 
        submissions = hackerrank_readSubmissions(driver)
        #
        for key, val in submissions.items() :
            *_, code_href = val
            submissions[key].extend(readCode(driver, code_href))
        writeToExcel(submissions, output_filename)
        print ('result written to ' + output_filename)
    finally :
        #pickle.dump(submissions, open('submissions_debug.pickle', 'wb')) # useful for testing....
        driver.quit() # kills the browser...
# main

if __name__ == "__main__" :
    #submissions = pickle.load(open('submissions_debug.pickle', 'rb')) # useful for testing the Excel output
    #writeToExcel(submissions, 'testing.xlsx')
    try :
        main()
    except KeyboardInterrupt : print ('<ctrl>-c')
    quit()