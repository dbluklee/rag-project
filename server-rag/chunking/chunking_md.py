from langchain_text_splitters import MarkdownHeaderTextSplitter
from typing import List
import os

def chunk_markdown_file(file_path: str) -> List:
    # 주어진 경로의 마크다운 파일을 읽어 H1(#), H2(##) 헤더를 기준으로 분할.

    filename = os.path.basename(file_path)
    print(f"\n📖 마크다운 파일 처리: {filename}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
    except FileNotFoundError:
        print(f"❌ 오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return []
    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")
        return []

    # 분할 기준이 될 헤더를 정의
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
    ]

    # MarkdownHeaderTextSplitter 초기화
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, 
        return_each_line=False
    )

    # 텍스트 분할 실행
    print(f"\n✂️ 마크다운 헤더 기준으로 분할 중...")
    initial_chunks = markdown_splitter.split_text(markdown_text)
    print(f"📊 초기 분할 결과: {len(initial_chunks)}개 청크")

    # 메타데이터 후처리
    processed_chunks = []
    for i, chunk in enumerate(initial_chunks):
        chunk.metadata['source'] = filename
        
        # Header 2가 있는 경우에만 feature 추가
        header2 = chunk.metadata.get('Header 2', '')
        if header2:
            new_page_content = f'\n---\nfeature: {header2}\n{chunk.page_content}'
        else:
            new_page_content = f'\n---\nfeature: Unknown\n{chunk.page_content}'
            
        chunk.page_content = new_page_content
        processed_chunks.append(chunk)
        
        # print(f"   처리된 청크 {i+1}: feature='{header2 if header2 else 'Unknown'}'")

    print(f"\n✅ 총 {len(processed_chunks)}개 청크 처리 완료")
    return processed_chunks