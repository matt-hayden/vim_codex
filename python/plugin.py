import urllib, urllib.request
import json
import os
import sys

try:
    import vim
except:
    print("No vim module available outside vim")
    pass


from openai import OpenAI

client = None

MAX_SUPPORTED_INPUT_LENGTH = 4096
USE_STREAM_FEATURE = True
MAX_TOKENS_DEFAULT = 64


def initialize_openai_api():
    """
    Initialize the OpenAI API
    """
    global client
    client = OpenAI()


def complete_input_max_length(input_prompt, max_input_length=MAX_SUPPORTED_INPUT_LENGTH, stop=None, max_tokens=64):
    input_prompt = input_prompt[-max_input_length:]
    response = client.completions.create(model='gpt-3.5-turbo-instruct', prompt=input_prompt, best_of=1, temperature=0.5, max_tokens=max_tokens, stream=USE_STREAM_FEATURE, stop=stop)
    return response

def complete_input(input_prompt, stop, max_tokens):
    try:
        response = complete_input_max_length(input_prompt, int(2.5 * MAX_SUPPORTED_INPUT_LENGTH), stop=stop, max_tokens=max_tokens)
    except openai.InvalidRequestError:
        response = complete_input_max_length(input_prompt, MAX_SUPPORTED_INPUT_LENGTH, stop=stop, max_tokens=max_tokens)
        print('Using shorter input.')

    return response

def get_max_tokens():
    max_tokens = None
    if vim.eval('exists("a:max_tokens")') == '1':
        max_tokens_str = vim.eval('a:max_tokens')
        if max_tokens_str:
            max_tokens = int(max_tokens_str)

    if not max_tokens:
        max_tokens = MAX_TOKENS_DEFAULT

    return max_tokens

def delete_current_line_if_empty_and_stop_below_matches_stop_string(stop):
    vim_buf = vim.current.buffer
    row, col = vim.current.window.cursor
    if row == len(vim_buf):
        return
    # Get next none empty line using get_first_line_below_cursor_with_text
    next_line = get_first_line_below_cursor_with_text()
    if next_line == stop:
        if len(vim_buf[row-1]) == 0:
            vim_buf[row-1:row] = []

def delete_empty_inserted_lines_if_stop_matches_stop_string(stop):
    vim_buf = vim.current.buffer
    row, col = vim.current.window.cursor
    if row == len(vim_buf):
        return
    # Get next none empty line using get_first_line_below_cursor_with_text
    next_line = get_first_line_below_cursor_with_text()
    if next_line == stop:
        while True:
            if row >= len(vim_buf):
                break
            # Print the number of lines.
            if len(vim_buf[row-1]) == 0:
                vim_buf[row-1:row] = []
            else:
                break
        if len(vim_buf[row-1]) == 0:
            vim_buf[row-1:row] = []

def get_first_line_below_cursor_with_text():
    vim_buf = vim.current.buffer
    row, col = vim.current.window.cursor
    while True:
        if row == len(vim_buf):
            return None
        if len(vim_buf[row]) > 0:
            return vim_buf[row]
        row += 1


def create_completion(stop=None): 
    if client is None:
        initialize_openai_api()
    max_tokens = get_max_tokens()
    vim_buf = vim.current.buffer
    input_prompt = '\n'.join(vim_buf[:])
    
    row, col = vim.current.window.cursor
    input_prompt = '\n'.join(vim_buf[row:])
    input_prompt += '\n'.join(vim_buf[:row-1])
    input_prompt += '\n' + vim_buf[row-1][:col]
    if not stop:
        stop = get_first_line_below_cursor_with_text()
    response = complete_input(input_prompt, stop=stop, max_tokens=max_tokens)
    write_response(response, stop=stop)

def write_response(response, stop):
    vim_buf = vim.current.buffer
    vim_win = vim.current.window
    while True:
       # TODO: Fix bug that causes Vim to freeze when arrow keys are used.
       # Check if the user pressed any key.
        if vim_win.cursor[0] > len(vim_buf):
            return
        if vim_win.cursor[0] == len(vim_buf) and vim_win.cursor[1] > len(vim_buf[-1]):
            return
        if vim.eval('getchar(0)') != '0':
            return

        if USE_STREAM_FEATURE:
            single_response = next(response)
        else:
            single_response = response
        completion = single_response.choices[0].text
        if single_response.choices[0].finish_reason != None:
            if stop == '\n':
                completion += '\n'
        row, col = vim.current.window.cursor
        current_line = vim.current.buffer[row-1]
        new_line = current_line[:col] + completion + current_line[col:]
        if not USE_STREAM_FEATURE:
            if new_line == '':
                new_line = new_line
            elif new_line[-1] == '\n':
                new_line = new_line[:-1]
        new_lines = new_line.split('\n')
        new_lines.reverse()
        if len(vim_buf) == row:
            vim_buf.append('')
               
        vim_buf[row-1] = None
        cursor_pos_base = tuple(vim_win.cursor)
        for row_i in range(len(new_lines)):
            vim.current.buffer[row-1:row-1] = [new_lines[row_i]]

        if new_line == '':
            cursor_target_col = 0
        elif new_line[-1] != '\n':
            cursor_target_col = len(new_lines[0])
        else:
            cursor_target_col = 0
        vim_win.cursor = (cursor_pos_base[0] + row_i, cursor_target_col)

        if not USE_STREAM_FEATURE:
            break

        # Flush the vim buffer.
        vim.command("redraw")
        if USE_STREAM_FEATURE:
            if single_response.choices[0].finish_reason != None:
                # delete_current_line_if_empty_and_stop_below_matches_stop_string(stop)
                delete_empty_inserted_lines_if_stop_matches_stop_string(stop)
                break


