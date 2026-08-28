from __future__ import annotations


def counter_token(counter: int) -> str:
    """Retorna as 10 posições após o prefixo, usando letras quando os dígitos acabam."""
    if counter < 1:
        raise ValueError("O contador deve ser maior que zero.")
    numeric_capacity = 10**10
    if counter < numeric_capacity:
        return f"{counter:010d}"

    remaining = counter - numeric_capacity
    for letter_count in range(1, 11):
        digit_count = 10 - letter_count
        numbers_per_prefix = 10**digit_count
        tier_capacity = (26**letter_count) * numbers_per_prefix
        if remaining < tier_capacity:
            prefix_index, numeric_value = divmod(remaining, numbers_per_prefix)
            letters = []
            for position in range(letter_count - 1, -1, -1):
                divisor = 26**position
                letter_value, prefix_index = divmod(prefix_index, divisor)
                letters.append(chr(ord("A") + letter_value))
            number = f"{numeric_value:0{digit_count}d}" if digit_count else ""
            return "".join(letters) + number
        remaining -= tier_capacity
    raise ValueError("A capacidade máxima do contador foi atingida.")


def identifier_for_counter(counter: int, prefix: str) -> str:
    return f"{prefix}{counter_token(counter)}"


def visible_counter(counter: int) -> str:
    token = counter_token(counter)
    return f"{counter:05d}" if token.isdigit() else token
