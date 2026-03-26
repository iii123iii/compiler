class Parser:
    def __init__(self):
        self.data_lines = ["section .data", "    newline db 10", "    newlineLen equ $ - newline"]
        self.bss_lines = ["section .bss"]

        self.main_lines = []
        self.functions = {}
        self.current_function = None

        self.symbols = {}
        self.num_symbols = {}
        self.literal_counter = 0
        self.var_counter = 0
        self.input_counter = 0
        self.label_counter = 0
        self.if_stack = []
        self.loop_stack = []

    @staticmethod
    def _escape_for_nasm(text):
        escaped = []
        for ch in text:
            if ch == "\\":
                escaped.append("\\\\")
            elif ch == "'":
                escaped.append("\\'")
            else:
                escaped.append(ch)
        return "".join(escaped)

    @staticmethod
    def _is_identifier(name):
        if not name:
            return False
        if not (name[0].isalpha() or name[0] == "_"):
            return False
        return all(ch.isalnum() or ch == "_" for ch in name)

    def _extract_text(self, parts):
        raw = " ".join(parts)
        if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
            return raw[1:-1]
        return raw

    def _target_lines(self):
        return self.main_lines if self.current_function is None else self.functions[self.current_function]

    def _new_literal(self, text):
        label = f"lit{self.literal_counter}"
        self.literal_counter += 1
        escaped = self._escape_for_nasm(text)
        self.data_lines.append(f"    {label} db '{escaped}'")
        self.data_lines.append(f"    {label}Len equ $ - {label}")
        return {"kind": "static", "label": label, "len": f"{label}Len"}

    def _emit_write(self, symbol, line):
        target = self._target_lines()
        target.append(f"    ; write from line {line}")
        target.append("    mov rax, 1")
        target.append("    mov rdi, 1")
        target.append(f"    mov rsi, {symbol['label']}")
        target.append(f"    mov rdx, {symbol['len']}" if symbol["kind"] == "static" else f"    mov rdx, [{symbol['len']}]")
        target.append("    syscall")

    def _resolve_value(self, parts, line):
        if not parts:
            raise ValueError(f"line {line}: missing value")
        if len(parts) == 1 and parts[0] in self.symbols:
            return self.symbols[parts[0]]
        return self._new_literal(self._extract_text(parts))

    def _ensure_num_symbol(self, name, line):
        if not self._is_identifier(name):
            raise ValueError(f"line {line}: invalid numeric identifier '{name}'")
        if name not in self.num_symbols:
            label = f"num_{name}_{self.var_counter}"
            self.var_counter += 1
            self.bss_lines.append(f"    {label} resq 1")
            self.num_symbols[name] = label
        return self.num_symbols[name]

    def _emit_read_input(self, name, prompt_parts, line, as_number=False):
        if not self._is_identifier(name):
            raise ValueError(f"line {line}: invalid identifier '{name}'")

        if prompt_parts:
            self._emit_write(self._new_literal(self._extract_text(prompt_parts)), line)

        buffer_label = f"inbuf_{name}_{self.input_counter}"
        len_label = f"inlen_{name}_{self.input_counter}"
        self.input_counter += 1

        self.bss_lines.append(f"    {buffer_label} resb 256")
        self.bss_lines.append(f"    {len_label} resq 1")
        self.symbols[name] = {"kind": "dynamic", "label": buffer_label, "len": len_label}

        read_loop = f".read_loop_{self.label_counter}"
        read_done = f".read_done_{self.label_counter}"
        self.label_counter += 1

        target = self._target_lines()
        target.append(f"    ; input from line {line}")
        target.extend([
            "    xor r12, r12",
            f"{read_loop}:",
            "    mov rax, 0",
            "    mov rdi, 0",
            f"    lea rsi, [{buffer_label} + r12]",
            "    mov rdx, 1",
            "    syscall",
            "    cmp rax, 0",
            f"    jle {read_done}",
            f"    cmp byte [{buffer_label} + r12], 10",
            f"    je {read_done}",
            "    inc r12",
            "    cmp r12, 255",
            f"    jl {read_loop}",
            f"{read_done}:",
            f"    mov [{len_label}], r12",
        ])

        if as_number:
            num_label = self._ensure_num_symbol(name, line)
            conv_loop = f".num_conv_{self.label_counter}"
            conv_done = f".num_done_{self.label_counter}"
            self.label_counter += 1
            target.extend([
                "    xor rax, rax",
                f"    mov rcx, [{len_label}]",
                f"    mov rsi, {buffer_label}",
                f"{conv_loop}:",
                "    cmp rcx, 0",
                f"    je {conv_done}",
                "    movzx rdx, byte [rsi]",
                "    sub rdx, '0'",
                "    imul rax, rax, 10",
                "    add rax, rdx",
                "    inc rsi",
                "    dec rcx",
                f"    jmp {conv_loop}",
                f"{conv_done}:",
                f"    mov [{num_label}], rax",
            ])

    def _start_function(self, name, line):
        if self.current_function is not None:
            raise ValueError(f"line {line}: nested functions are not allowed")
        if not self._is_identifier(name):
            raise ValueError(f"line {line}: invalid function name '{name}'")
        if name in self.functions:
            raise ValueError(f"line {line}: function '{name}' already defined")
        self.functions[name] = []
        self.current_function = name

    def _end_function(self, line):
        if self.current_function is None:
            raise ValueError(f"line {line}: endfunc without matching func")
        if self.if_stack or self.loop_stack:
            raise ValueError(f"line {line}: close all if/loop blocks before endfunc")
        body = self.functions[self.current_function]
        if not body or body[-1].strip() != "ret":
            body.append("    ret")
        self.current_function = None

    def _emit_random(self, name, low, high, line):
        if low < 0 or high > 9 or low > high:
            raise ValueError(f"line {line}: random only supports ranges 0..9 with min <= max")
        if not self._is_identifier(name):
            raise ValueError(f"line {line}: invalid identifier '{name}'")

        buffer_label = f"randbuf_{name}_{self.input_counter}"
        len_label = f"randlen_{name}_{self.input_counter}"
        self.input_counter += 1
        self.bss_lines.append(f"    {buffer_label} resb 2")
        self.bss_lines.append(f"    {len_label} resq 1")
        self.symbols[name] = {"kind": "dynamic", "label": buffer_label, "len": len_label}

        target = self._target_lines()
        target.extend([
            f"    ; random from line {line}",
            "    rdtsc",
            "    xor edx, edx",
            f"    mov ecx, {high - low + 1}",
            "    div ecx",
            f"    add edx, {low}",
            "    add dl, '0'",
            f"    mov [{buffer_label}], dl",
            f"    mov qword [{len_label}], 1",
        ])


    def _emit_random_num(self, name, low, high, line):
        if low > high:
            raise ValueError(f"line {line}: randomnum requires min <= max")
        label = self._ensure_num_symbol(name, line)
        target = self._target_lines()
        target.extend([
            f"    ; randomnum from line {line}",
            "    rdtsc",
            "    xor rdx, rdx",
            f"    mov rcx, {high - low + 1}",
            "    div rcx",
            f"    add rdx, {low}",
            f"    mov [{label}], rdx",
        ])

    def _emit_string_if_start(self, left_parts, right_parts, line):
        left = self._resolve_value(left_parts, line)
        right = self._resolve_value(right_parts, line)
        end_label = f"if_end_{self.label_counter}"
        cmp_loop = f"if_cmp_{self.label_counter}"
        cmp_done = f"if_done_{self.label_counter}"
        self.label_counter += 1
        self.if_stack.append(end_label)

        target = self._target_lines()
        target.append(f"    ; ifeq from line {line}")
        target.append(f"    mov r8, {left['len']}" if left["kind"] == "static" else f"    mov r8, [{left['len']}]")
        target.append(f"    mov r9, {right['len']}" if right["kind"] == "static" else f"    mov r9, [{right['len']}]")
        target.extend([
            "    cmp r8, r9",
            f"    jne {end_label}",
            "    mov rcx, r8",
            f"    mov rsi, {left['label']}",
            f"    mov rdi, {right['label']}",
            f"{cmp_loop}:",
            "    cmp rcx, 0",
            f"    je {cmp_done}",
            "    mov al, [rsi]",
            "    mov bl, [rdi]",
            "    cmp al, bl",
            f"    jne {end_label}",
            "    inc rsi",
            "    inc rdi",
            "    dec rcx",
            f"    jmp {cmp_loop}",
            f"{cmp_done}:",
        ])

    def _resolve_num_operand(self, token, line):
        if token in self.num_symbols:
            return ("mem", self.num_symbols[token])
        try:
            return ("imm", int(token))
        except ValueError as exc:
            raise ValueError(f"line {line}: numeric operand must be a number or numeric variable") from exc

    def _emit_numeric_if_start(self, op, left_token, right_token, line):
        left_kind, left_val = self._resolve_num_operand(left_token, line)
        right_kind, right_val = self._resolve_num_operand(right_token, line)

        end_label = f"if_num_end_{self.label_counter}"
        self.label_counter += 1
        self.if_stack.append(end_label)

        target = self._target_lines()
        target.append(f"    ; {op} from line {line}")
        target.append(f"    mov r8, [{left_val}]" if left_kind == "mem" else f"    mov r8, {left_val}")
        target.append(f"    mov r9, [{right_val}]" if right_kind == "mem" else f"    mov r9, {right_val}")
        target.append("    cmp r8, r9")
        jump = {"ifnumeq": "jne", "ifnumgt": "jle", "ifnumlt": "jge"}[op]
        target.append(f"    {jump} {end_label}")

    def _emit_endif(self, line):
        if not self.if_stack:
            raise ValueError(f"line {line}: endif without matching if")
        self._target_lines().append(f"{self.if_stack.pop()}:")

    def _emit_repeat_start(self, count, line):
        if count <= 0:
            raise ValueError(f"line {line}: repeat count must be > 0")
        lid = self.label_counter
        self.label_counter += 1
        cnt = f"loopcnt_{lid}"
        start = f"loop_start_{lid}"
        end = f"loop_end_{lid}"
        self.bss_lines.append(f"    {cnt} resq 1")
        self.loop_stack.append({"kind": "repeat", "counter": cnt, "start": start, "end": end})
        target = self._target_lines()
        target.append(f"    mov qword [{cnt}], {count}")
        target.append(f"{start}:")

    def _emit_loop_start(self):
        lid = self.label_counter
        self.label_counter += 1
        start = f"forever_start_{lid}"
        end = f"forever_end_{lid}"
        self.loop_stack.append({"kind": "forever", "start": start, "end": end})
        self._target_lines().append(f"{start}:")

    def _emit_loop_end(self, line):
        if not self.loop_stack:
            raise ValueError(f"line {line}: endloop/endrepeat without matching loop")
        ctx = self.loop_stack.pop()
        target = self._target_lines()
        if ctx["kind"] == "repeat":
            target.append(f"    dec qword [{ctx['counter']}]")
            target.append(f"    jnz {ctx['start']}")
        else:
            target.append(f"    jmp {ctx['start']}")
        target.append(f"{ctx['end']}:")

    def _emit_break(self, line):
        if not self.loop_stack:
            raise ValueError(f"line {line}: break outside of a loop")
        self._target_lines().append(f"    jmp {self.loop_stack[-1]['end']}")

    def parse(self, tokens, line):
        if not tokens:
            return
        instruction = tokens[0].lower()

        if instruction in {"print", "println", "say"}:
            if len(tokens) < 2:
                raise ValueError(f"line {line}: {instruction} expects an argument")
            self._emit_write(self._resolve_value(tokens[1:], line), line)
            self._emit_write({"kind": "static", "label": "newline", "len": "newlineLen"}, line)
            return

        if instruction in {"printraw", "write"}:
            if len(tokens) < 2:
                raise ValueError(f"line {line}: {instruction} expects an argument")
            self._emit_write(self._resolve_value(tokens[1:], line), line)
            return

        if instruction in {"let", "set"}:
            if len(tokens) < 4 or tokens[2] != "=":
                raise ValueError(f"line {line}: expected syntax let/set <name> = <value>")
            name = tokens[1]
            if not self._is_identifier(name):
                raise ValueError(f"line {line}: invalid identifier '{name}'")
            lit = self._new_literal(self._extract_text(tokens[3:]))
            self.symbols[name] = lit
            return

        if instruction in {"num", "setnum"}:
            if len(tokens) != 4 or tokens[2] != "=":
                raise ValueError(f"line {line}: expected syntax num <name> = <integer>")
            label = self._ensure_num_symbol(tokens[1], line)
            try:
                value = int(tokens[3])
            except ValueError as exc:
                raise ValueError(f"line {line}: num value must be integer") from exc
            self._target_lines().append(f"    mov qword [{label}], {value}")
            return

        if instruction in {"input", "ask"}:
            if len(tokens) < 2:
                raise ValueError(f"line {line}: expected syntax input/ask <name> [prompt]")
            self._emit_read_input(tokens[1], tokens[2:], line, as_number=False)
            return

        if instruction in {"inputnum", "asknum"}:
            if len(tokens) < 2:
                raise ValueError(f"line {line}: expected syntax inputnum/asknum <name> [prompt]")
            self._emit_read_input(tokens[1], tokens[2:], line, as_number=True)
            return

        if instruction in {"random", "rand"}:
            if len(tokens) != 4:
                raise ValueError(f"line {line}: expected syntax random <name> <min> <max>")
            self._emit_random(tokens[1], int(tokens[2]), int(tokens[3]), line)
            return

        if instruction in {"randomnum", "randnum"}:
            if len(tokens) != 4:
                raise ValueError(f"line {line}: expected syntax randomnum <name> <min> <max>")
            self._emit_random_num(tokens[1], int(tokens[2]), int(tokens[3]), line)
            return

        if instruction in {"func", "function"}:
            if len(tokens) != 2:
                raise ValueError(f"line {line}: expected syntax func/function <name>")
            self._start_function(tokens[1], line)
            return

        if instruction in {"endfunc", "endfunction"}:
            self._end_function(line)
            return

        if instruction == "call":
            if len(tokens) != 2:
                raise ValueError(f"line {line}: expected syntax call <name>")
            self._target_lines().append(f"    call func_{tokens[1]}")
            return

        if instruction == "return":
            if self.current_function is None:
                raise ValueError(f"line {line}: return is only valid inside a function")
            self._target_lines().append("    ret")
            return

        if instruction == "ifeq":
            if len(tokens) < 3:
                raise ValueError(f"line {line}: expected syntax ifeq <left> <right>")
            self._emit_string_if_start([tokens[1]], tokens[2:], line)
            return

        if instruction in {"ifnumeq", "ifnumgt", "ifnumlt"}:
            if len(tokens) != 3:
                raise ValueError(f"line {line}: expected syntax {instruction} <left> <right>")
            self._emit_numeric_if_start(instruction, tokens[1], tokens[2], line)
            return

        if instruction == "endif":
            self._emit_endif(line)
            return

        if instruction == "repeat":
            if len(tokens) != 2:
                raise ValueError(f"line {line}: expected syntax repeat <count>")
            self._emit_repeat_start(int(tokens[1]), line)
            return

        if instruction in {"loop", "forever"}:
            self._emit_loop_start()
            return

        if instruction in {"endrepeat", "endloop", "endforever"}:
            self._emit_loop_end(line)
            return

        if instruction == "break":
            self._emit_break(line)
            return

        if instruction == "exit":
            if len(tokens) != 2:
                raise ValueError(f"line {line}: expected syntax exit <status_code>")
            code = int(tokens[1])
            if code < 0 or code > 255:
                raise ValueError(f"line {line}: exit code must be between 0 and 255")
            self._target_lines().extend(["    mov rax, 60", f"    mov rdi, {code}", "    syscall"])
            return

        raise ValueError(f"line {line}: unknown instruction '{instruction}'")

    def finish(self):
        if self.current_function is not None:
            raise ValueError(f"Unclosed function: {self.current_function}")
        if self.if_stack:
            raise ValueError("Unclosed if block")
        if self.loop_stack:
            raise ValueError("Unclosed loop block")

        self.main_lines.extend(["    mov rax, 60", "    xor rdi, rdi", "    syscall"])

        text = ["section .text", "global _start", "", "_start:"] + self.main_lines
        for name, body in self.functions.items():
            text.extend(["", f"func_{name}:"])
            text.extend(body)

        data = '\n'.join(self.data_lines)
        bss = '\n'.join(self.bss_lines)
        text_blob = '\n'.join(text)
        return f"{data}\n\n{bss}\n\n{text_blob}\n"
