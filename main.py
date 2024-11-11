from lexer import Lexer
from parser import Parser
import os

line = input("File> ")

data = '''section .data'''

start = ""

with open(line, 'r') as file:
    i = 0
    for line in file:
        line = line.strip()
        if not line:
            continue  

        print(f"Processing line {i}: {line}") 

        tokens = Lexer(line).lexer() 
        print(f"Tokens: {tokens}")  

        start, data = Parser(tokens, data, start, i).parse() 

        i += 1 


start += "\nmov eax, 1\nxor ebx, ebx\nint 0x80" 

code = f"{data}\n\nsection .text\nglobal _start\n\n_start:\n{start}"

with open("output.asm", "w") as f:
    f.write(code)

os.system("nasm -f elf64 output.asm -o output.o")
print("Linking output.asm")
os.remove("output.asm")
os.system("ld output.o -o output")
print("Generating executable")
os.remove("output.o")
