import sys

sys.stdout = open('regex_by_line.txt', 'w')
with open('regex.txt', 'r') as f:
    text = f.readline()
    p_num = 0
    pattern = ''
    for char in text:
        if p_num == 0:
            if '春节' in pattern:
                print(pattern)
            pattern = ''
        if char == '(':
            p_num += 1
        elif char == ')':
            p_num -= 1
        pattern += char
        
