import torch
from langchain_huggingface import HuggingFaceEmbeddings
import os

def get_bge_m3_model() -> HuggingFaceEmbeddings:
    """
    BGE-M3 임베딩 모델을 로드합니다.
    USE_CUDA 환경변수에 따라 CPU/GPU를 선택합니다.
    GPU 메모리 부족 시 에러를 발생시킵니다.
    """
    
    # USE_CUDA 환경변수 확인
    use_cuda = os.getenv('USE_CUDA', 'true').lower() == 'true'
    
    # USE_CUDA가 false면 CUDA_VISIBLE_DEVICES를 빈 문자열로 설정하여 GPU 비활성화
    if not use_cuda:
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        print("🔧 USE_CUDA=false - GPU 비활성화, CPU 모드로 전환")
        device = 'cpu'
    elif torch.cuda.is_available():
        # GPU 메모리 확인
        try:
            gpu_memory = torch.cuda.get_device_properties(0).total_memory
            gpu_free = torch.cuda.memory_reserved(0) - torch.cuda.memory_allocated(0)
            gpu_memory_gb = gpu_memory / (1024**3)
            gpu_free_gb = gpu_free / (1024**3)
            
            print(f"🔍 GPU 전체 메모리: {gpu_memory_gb:.1f}GB")
            print(f"🔍 GPU 여유 메모리: {gpu_free_gb:.1f}GB")
            
            # 여유 메모리가 2GB 미만이면 에러 발생
            if gpu_free_gb < 2.0:
                raise RuntimeError(
                    f"❌ GPU 메모리 부족! 여유 메모리: {gpu_free_gb:.1f}GB < 2.0GB 필요\n"
                    f"해결방법:\n"
                    f"1. 다른 GPU 프로세스 종료\n"
                    f"2. USE_CUDA=false로 설정하여 CPU 모드 사용\n"
                    f"3. 더 큰 GPU 메모리 환경 사용"
                )
            else:
                device = 'cuda'
        except Exception as e:
            # GPU 상태 확인 자체가 실패한 경우에만 CPU로 전환
            if "CUDA" in str(e) or "GPU" in str(e):
                raise RuntimeError(
                    f"❌ GPU 확인 실패: {e}\n"
                    f"해결방법:\n"
                    f"1. NVIDIA 드라이버 확인\n" 
                    f"2. CUDA 설치 확인\n"
                    f"3. USE_CUDA=false로 설정하여 CPU 모드 사용"
                )
            else:
                raise e
    else:
        raise RuntimeError(
            "❌ CUDA를 사용할 수 없습니다!\n"
            "해결방법:\n"
            "1. NVIDIA GPU 및 드라이버 설치 확인\n"
            "2. CUDA 설치 확인\n" 
            "3. USE_CUDA=false로 설정하여 CPU 모드 사용"
        )
    
    print(f"🔧 임베딩 모델 디바이스: {device}")
    
    model_name = 'BAAI/bge-m3'
    model_kwargs = {'device': device}
    encode_kwargs = {'normalize_embeddings': True}
    
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        print(f"✅ 임베딩 모델 로딩 완료 ({device})")
        return embeddings
    except Exception as e:
        raise RuntimeError(
            f"❌ 임베딩 모델 로딩 실패: {e}\n"
            f"해결방법:\n"
            f"1. 인터넷 연결 확인 (HuggingFace 모델 다운로드)\n"
            f"2. 디스크 공간 확인\n"
            f"3. USE_CUDA=false로 설정하여 CPU 모드 시도"
        )