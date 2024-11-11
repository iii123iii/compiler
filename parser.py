class Parser:
    def __init__(self, tokens, data, start, line):
        self.tokens = tokens
        self.data = data
        self.start = start
        self.line = line

    def parse(self):
        print(f"Parsing line {self.line}: {self.tokens}")
        
        if self.tokens[0] == "print":
            text = " ".join(self.tokens[1:])
            
            label = f"print{self.line}"
            self.data += f"\n {label} db '{text}', 10, 0"
            self.data += f"\n {label}Len equ $ - {label}"

            self.start += f"""
            mov eax, 4 ; syscall
            mov ebx, 1 ; stdout
            mov ecx, {label} ; pointer to the text
            mov edx, {label}Len ; text length
            int 0x80 ; syscall
            """

        return self.start, self.data
