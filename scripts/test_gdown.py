import gdown

url = 'https://drive.google.com/drive/folders/1jU7qgDqU1je9Y0PMKJ_f31yXRo5uWGFm'
try:
    files = gdown.download_folder(url=url, skip_download=True, quiet=False)
    print("Files found in folder:", len(files))
    for f in files:
        print(" -", getattr(f, 'path', str(f)))
except Exception as e:
    print("Error:", e)
