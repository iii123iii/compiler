class Lexer:
    """Tokenize a single source line.

    Supports:
    - whitespace-delimited tokens
    - quoted strings with basic escapes (\\n, \\t, \\r, \\" and \\\\)
    - inline comments starting with # outside of quoted strings
    - standalone '=' and ',' tokens outside of strings
    """

    def __init__(self, line):
        self.line = line

    def lexer(self):
        tokens = []
        token = []
        in_string = False
        escaped = False

        def flush_token():
            if token:
                tokens.append("".join(token))
                token.clear()

        for char in self.line:
            if in_string:
                if escaped:
                    if char == "n":
                        token.append("\n")
                    elif char == "t":
                        token.append("\t")
                    elif char == "r":
                        token.append("\r")
                    elif char == '"':
                        token.append('"')
                    elif char == "\\":
                        token.append("\\")
                    else:
                        token.append(char)
                    escaped = False
                    continue

                if char == "\\":
                    escaped = True
                elif char == '"':
                    tokens.append(f'"{"".join(token)}"')
                    token.clear()
                    in_string = False
                else:
                    token.append(char)
                continue

            if char == "#":
                break

            if char.isspace():
                flush_token()
                continue

            if char in {"=", ","}:
                flush_token()
                tokens.append(char)
                continue

            if char == '"':
                flush_token()
                in_string = True
                escaped = False
                token.clear()
                continue

            token.append(char)

        if in_string:
            raise ValueError("Unterminated string literal")

        flush_token()
        return tokens
