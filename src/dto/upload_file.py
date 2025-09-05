import io


class MockUploadFile:
    def __init__(self, content, filename, file_ext):
        # 处理不同类型的content：bytes或者有getvalue方法的对象
        if isinstance(content, bytes):
            self.file = io.BytesIO(content)
        else:
            self.file = content
        
        self.filename = filename
        # 根据扩展名设置内容类型
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", 
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png", 
            "gif": "image/gif",
            "webp": "image/webp"
        }
        self.content_type = content_types.get(file_ext, "image/jpeg")
    
    async def read(self):
        if hasattr(self.file, 'getvalue'):
            return self.file.getvalue()
        else:
            return self.file