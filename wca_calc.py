def parse_time(t_str: str) -> float:
    t_str = t_str.strip().strip("()[]").upper()
    if not t_str:
        raise ValueError("Empty time value")

    if t_str in ("DNF", "DNS"):
        return float('inf')

    if ":" in t_str:
        parts = t_str.split(":")
        return float(parts[0]) * 60.0 + float(parts[1])
    return float(t_str)

def format_time(seconds: float) -> str:
    if seconds == float('inf'):
        return "DNF"
    if seconds >= 60.0:
        return f"{int(seconds // 60)}:{seconds % 60:05.2f}"
    return f"{seconds:.2f}"

def calculate_ao(raw_input: str, expected_count: int) -> dict:
    tokens = raw_input.replace(",", " ").replace(";", " ").split()
    if len(tokens) != expected_count:
        raise ValueError(f"Expected {expected_count} times, but received {len(tokens)}.")

    times = []
    for t in tokens:
        try:
            times.append(parse_time(t))
        except Exception:
            raise ValueError(f"Could not parse '{t}' as a valid time.")

    sorted_indices = sorted(range(expected_count), key=lambda i: times[i])
    best_idx, worst_idx = sorted_indices[0], sorted_indices[-1]

    counting = [times[i] for i in range(expected_count) if i not in (best_idx, worst_idx)]
    avg = float('inf') if any(t == float('inf') for t in counting) else round(sum(counting) / len(counting), 2)

    solves = [
        f"{i + 1}. ({format_time(t)})" if i in (best_idx, worst_idx) else f"{i + 1}. {format_time(t)}"
        for i, t in enumerate(times)
    ]

    return {
        "average": format_time(avg),
        "solves": solves,
        "best": format_time(times[best_idx]),
        "worst": format_time(times[worst_idx]),
    }
