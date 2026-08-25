# MCP 개요

MCP(Model Context Protocol)는 AI 애플리케이션이 외부 도구와 데이터에 표준 방식으로 연결되도록 돕는 프로토콜입니다.

## 핵심 구성

- Tool: 파일 읽기, 계산, 데이터베이스 조회처럼 실행 가능한 기능입니다.
- Resource: 문서, 설정, 스키마처럼 읽을 수 있는 데이터입니다.
- Prompt: 반복해서 사용할 수 있는 프롬프트 템플릿입니다.

## 이 프로젝트에서 MCP의 역할

FastAPI는 일반 사용자와 REST 방식으로 통신합니다.
MCP Server는 MCP Client와 연결되어 파일, RAG, MySQL Tool을 제공합니다.
