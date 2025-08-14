"""
OpenWebUI API 인증 처리
"""
from fastapi import HTTPException, Header, status
from typing import Optional
import os

class AuthService:
    """인증 서비스"""
    
    def __init__(self):
        # 환경변수에서 인증 설정 가져오기
        self.auth_enabled = os.getenv('WEBUI_AUTH', 'false').lower() == 'true'
        self.api_key_enabled = os.getenv('ENABLE_API_KEY', 'false').lower() == 'true'
        
        # 개발용 고정 API 키 (실제로는 DB에서 관리)
        self.valid_api_keys = {
            "sk-cheeseade-dev-key-001": {
                "user_id": "dev-user",
                "name": "Development Key",
                "permissions": ["read", "write"]
            }
        }
        
        print(f"🔐 AuthService 초기화")
        print(f"   인증 활성화: {self.auth_enabled}")
        print(f"   API 키 활성화: {self.api_key_enabled}")
    
    def verify_api_key(self, authorization: Optional[str] = None) -> dict:
        """
        API 키 검증
        
        Returns:
            dict: 사용자 정보 (검증 성공시)
            
        Raises:
            HTTPException: 인증 실패시
        """
        # 인증이 비활성화된 경우
        if not self.auth_enabled and not self.api_key_enabled:
            return {
                "user_id": "anonymous",
                "name": "Anonymous User",
                "permissions": ["read", "write"]
            }
        
        # Authorization 헤더 확인
        if not authorization:
            # 인증이 선택사항인 경우 None 반환 허용
            if not self.auth_enabled:
                return {
                    "user_id": "anonymous",
                    "name": "Anonymous User", 
                    "permissions": ["read"]
                }
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "message": "API 키가 필요합니다. Authorization 헤더를 확인하세요.",
                        "type": "authentication_error",
                        "code": "missing_api_key"
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Bearer 토큰 형식 확인
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "message": "잘못된 인증 형식입니다. 'Bearer <api_key>' 형식을 사용하세요.",
                        "type": "authentication_error",
                        "code": "invalid_auth_format"
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # API 키 추출
        api_key = authorization[7:]  # "Bearer " 제거
        
        # API 키 검증
        user_info = self.valid_api_keys.get(api_key)
        if not user_info:
            # 개발 모드에서는 경고만 출력하고 통과
            if not self.auth_enabled:
                print(f"⚠️ 유효하지 않은 API 키이지만 개발 모드로 통과: {api_key[:10]}...")
                return {
                    "user_id": "dev-user",
                    "name": "Development User",
                    "permissions": ["read", "write"]
                }
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "message": "유효하지 않은 API 키입니다.",
                        "type": "authentication_error",
                        "code": "invalid_api_key"
                    }
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        print(f"✅ API 키 인증 성공: {user_info['name']}")
        return user_info
    
    def check_permission(self, user_info: dict, required_permission: str) -> bool:
        """권한 확인"""
        user_permissions = user_info.get("permissions", [])
        return required_permission in user_permissions
    
    def add_api_key(self, api_key: str, user_info: dict) -> bool:
        """API 키 추가 (동적 관리용)"""
        if api_key in self.valid_api_keys:
            return False
        
        self.valid_api_keys[api_key] = user_info
        print(f"➕ API 키 추가됨: {user_info.get('name', 'Unknown')}")
        return True
    
    def remove_api_key(self, api_key: str) -> bool:
        """API 키 제거"""
        if api_key in self.valid_api_keys:
            user_info = self.valid_api_keys.pop(api_key)
            print(f"➖ API 키 제거됨: {user_info.get('name', 'Unknown')}")
            return True
        return False

# 전역 인증 서비스 인스턴스
auth_service = AuthService()

# 의존성 함수 (FastAPI에서 사용)
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """현재 사용자 정보 반환 (FastAPI 의존성)"""
    return auth_service.verify_api_key(authorization)

async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """선택적 사용자 정보 반환 (인증 실패해도 None 반환)"""
    try:
        return auth_service.verify_api_key(authorization)
    except HTTPException:
        # 인증 실패시 None 반환 (선택적 인증)
        return None