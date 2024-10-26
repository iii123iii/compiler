from lexer import Lexer
from parser import Parser
import os as os

while True:
    line = input("o>")
    tokens = Lexer(line).lexer()

    parse = Parser(tokens).parse()

    file = open("output.asm", "w").write(parse)

    os.system("nasm -f elf64 output.asm -o output.o")
    os.remove("output.asm")
    os.system("ld output.o -o output")
    os.remove("output.o")