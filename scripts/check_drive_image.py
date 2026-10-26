import gdown

try:
    info = gdown.download(id="1cjY6HsHaSZuLVHywIxD5xQqng33J5S2b", output=None, quiet=False, format="json")
    print("Drive image archive info:", info)
except Exception as e:
    print("Drive image archive check:", e)
