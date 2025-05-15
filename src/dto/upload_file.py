class MockUploadFile:
    def __init__(self, content, filename, file_ext):
        self.file = content
        self.filename = filename
        # 根据扩展名设置内容类型
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        self.content_type = content_types.get(file_ext, "image/jpeg")
    
    async def read(self):
        return self.file.getvalue()