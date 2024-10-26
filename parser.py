class Parser:
    def __init__(self, tokens):
        self.tokens = tokens

    def parse(self):
        return f'''
                   section .data
                    message db '{self.tokens}', 10, 0\n
                    messageLen equ $ - message


                   section .text
                    global _start

                   _start:
                    mov eax, 4 ; syscall
                    mov ebx, 1 ; stdout
                    mov ecx, message ; message pointer
                    mov edx, messageLen ; message length
                    int 0x80 ; call kernal


                    mov eax, 1
                    xor ebx, ebx
                    int 0x80 
'''