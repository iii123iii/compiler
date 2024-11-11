class Lexer:
    def __init__(self, line):
        self.line = line
    
    def lexer(self):
        tokens = []
        chars = list(self.line)
        word = ""

        for i , char in enumerate(chars):
            if char.strip() == "":
                if word != "":
                    tokens.append(word)
                    word = ""
            else:
                word = word + char
        if word != "":
            tokens.append(word)



        return tokens