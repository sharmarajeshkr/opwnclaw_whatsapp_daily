from neonize.utils.jid import build_jid

numbers = [
    "919789824976",
    "+919789824976",
    "919789824976@s.whatsapp.net"
]

for n in numbers:
    try:
        jid = build_jid(n)
        print(f"Input: {n} -> Output: {jid!r}")
    except Exception as e:
        print(f"Input: {n} -> Error: {e}")
