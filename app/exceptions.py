class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500, error_code: str = "app_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在", error_code: str = "not_found"):
        super().__init__(message=message, status_code=404, error_code=error_code)


class DatabaseError(AppError):
    def __init__(self, message: str = "数据库操作失败", error_code: str = "database_error"):
        super().__init__(message=message, status_code=500, error_code=error_code)


class ModelInvocationError(AppError):
    def __init__(self, message: str = "模型调用失败", error_code: str = "model_invocation_error"):
        super().__init__(message=message, status_code=502, error_code=error_code)


class FileValidationError(AppError):
    def __init__(self, message: str = "上传文件不合法", error_code: str = "file_validation_error", status_code: int = 400):
        super().__init__(message=message, status_code=status_code, error_code=error_code)


class FileProcessingError(AppError):
    def __init__(self, message: str = "文件解析失败", error_code: str = "file_processing_error"):
        super().__init__(message=message, status_code=422, error_code=error_code)
