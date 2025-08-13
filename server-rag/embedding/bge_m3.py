import torch
from langchain_huggingface import HuggingFaceEmbeddings
import os

def get_bge_m3_model() -> HuggingFaceEmbeddings:
    """
    BGE-M3 임베딩 모델을 로드합니다.
    환경변수나 메모리 상황에 따라 CPU/GPU를 선택합니다.
    """
    
    # 환경변수로 CPU 강제 설정 확인
    force_cpu = os.getenv('FORCE_CPU', 'false').lower() == 'true'
    cuda_visible = os.getenv('CUDA_VISIBLE_DEVICES', '')
    
    if force_cpu or cuda_visible == '':
        print("🔧 환경변수에 의해 CPU 사용으로 설정됨")
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
            
            # 여유 메모리가 2GB 미만이면 CPU 사용
            if gpu_free_gb < 2.0:
                print("⚠️ GPU 메모리 부족 - CPU 사용으로 전환")
                device = 'cpu'
            else:
                device = 'cuda'
        except:
            print("⚠️ GPU 상태 확인 실패 - CPU 사용")
            device = 'cpu'
    else:
        print("⚠️ CUDA 사용 불가 - CPU 사용")
        device = 'cpu'
    
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
        if device == 'cuda':
            print(f"❌ GPU 로딩 실패: {e}")
            print("🔄 CPU로 재시도...")
            model_kwargs = {'device': 'cpu'}
            embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs
            )
            print("✅ 임베딩 모델 로딩 완료 (CPU 대체)")
            return embeddings
        else:
            raise e