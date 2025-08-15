"""
OpenWebUI API 인증 처리 - 완전한 비활성화 버전
"""
from fastapi import HTTPException, Header, status
from typing import Optional
import os

class AuthService:
    """인증 서비스 - 완전 비활성화"""
    
    def __init__(self):
        
        self.auth_enabled = os.environ["WEBUI_AUTH"]
        self.api_key_enabled = os.environ["ENABLE_API_KEY"]
        
        print(f"🔐 AuthService 초기화 ")
        print(f"   인증 활성화: {self.auth_enabled}")
        print(f"   API 키 활성화: {self.api_key_enabled}")
    
    def verify_api_key(self, authorization: Optional[str] = None) -> dict:
        """
        API 키 검증 - 항상 익명 사용자 반환
        """
        # 항상 익명 사용자로 통과
        return {
            "user_id": "anonymous",
            "name": "Anonymous User",
            "permissions": ["read", "write"]
        }
    
    def check_permission(self, user_info: dict, required_permission: str) -> bool:
        """권한 확인 - 항상 True 반환"""
        return True

# 전역 인증 서비스 인스턴스
auth_service = AuthService()

# 의존성 함수 (FastAPI에서 사용) - 완전 비활성화 버전
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """현재 사용자 정보 반환 - 항상 익명 사용자"""
    return {
        "user_id": "anonymous",
        "name": "Anonymous User",
        "permissions": ["read", "write"]
    }

async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """선택적 사용자 정보 반환 - 항상 익명 사용자"""
    return {
        "user_id": "anonymous",
        "name": "Anonymous User",
        "permissions": ["read", "write"]
    }