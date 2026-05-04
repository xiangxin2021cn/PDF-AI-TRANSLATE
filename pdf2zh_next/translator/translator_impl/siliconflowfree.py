import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

import httpx
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.translator.base_rate_limiter import BaseRateLimiter
from pdf2zh_next.translator.base_translator import BaseTranslator
from pdf2zh_next.translator.rate_limiter.qps_rate_limiter import QPSRateLimiter
from tenacity import before_sleep_log
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    pass


class ServerNotAvailableError(Exception):
    pass


AVAILABLE_SERVER_ENDPOINTS = [
    "https://api1.pdf2zh-next.com/chatproxy",
    "https://api2.pdf2zh-next.com/chatproxy",
]


class SiliconFlowFreeTranslator(BaseTranslator):
    # https://github.com/openai/openai-python
    name = "siliconflowfree"

    def __init__(
        self,
        settings: SettingsModel,
        rate_limiter: BaseRateLimiter,
    ):
        self.settings = settings
        super().__init__(settings, rate_limiter)
        self.client = httpx.Client()

        self.url = AVAILABLE_SERVER_ENDPOINTS[0]
        self.get_fast_service()
        self.fetch_setting_and_update()

    def fetch_setting_and_update(self):
        try:
            response = self.client.get(f"{self.url}/config")
            if response.status_code == 200:
                resp = response.json()
                if resp["status"] == "ok":
                    qps = resp["qps"]
                    max_pool_size = resp["max_pool_size"]

                    assert isinstance(qps, int)
                    assert isinstance(max_pool_size, int)

                    assert qps > 0
                    assert max_pool_size > 0

                    self.settings.translation.qps = qps
                    self.settings.translation.pool_max_workers = max_pool_size

                    if isinstance(self.rate_limiter, QPSRateLimiter):
                        self.rate_limiter.set_max_qps(qps)
                        logger.info(f"Updated QPS rate limiter to {qps}")
                    logger.info(
                        f"Fetched setting and updated: qps: {qps}, max_pool_size: {max_pool_size}"
                    )

        except Exception as e:
            logger.error(f"Failed to fetch setting and update: {e}")

    def get_fast_service(self):
        """Find the fastest responding endpoint by sending parallel requests."""

        def test_endpoint_speed(endpoint):
            """Test a single endpoint 3 times and return (endpoint, total_response_time, success)."""
            total_response_time = 0
            success_count = 0

            for i in range(3):
                start_time = time.time()
                success = self.check_server_status(endpoint)
                response_time = time.time() - start_time
                total_response_time += response_time

                if success:
                    success_count += 1

                logger.debug(
                    f"Endpoint {endpoint} test {i + 1}/3: {response_time:.3f}s, success: {success}"
                )

            # Consider endpoint successful if at least 2 out of 3 tests succeed
            overall_success = success_count >= 2

            if not overall_success:
                total_response_time = float("inf")

            logger.info(
                f"Endpoint {endpoint} overall: {total_response_time:.3f}s total, {success_count}/3 successes"
            )
            return (endpoint, total_response_time, overall_success)

        # Test all endpoints in parallel
        fastest_endpoint = None
        fastest_time = float("inf")

        with ThreadPoolExecutor(
            max_workers=len(AVAILABLE_SERVER_ENDPOINTS)
        ) as executor:
            # Submit all endpoint tests
            future_to_endpoint = {
                executor.submit(test_endpoint_speed, endpoint): endpoint
                for endpoint in AVAILABLE_SERVER_ENDPOINTS
            }

            # Get results as they complete
            for future in as_completed(future_to_endpoint):
                endpoint, response_time, success = future.result()

                if success and response_time < fastest_time:
                    fastest_time = response_time
                    fastest_endpoint = endpoint
                    logger.info(
                        f"Found faster endpoint: {endpoint} ({response_time:.3f}s)"
                    )

        # Update the URL to use the fastest endpoint
        if fastest_endpoint:
            self.url = fastest_endpoint
            logger.info(
                f"Selected fastest endpoint: {fastest_endpoint} ({fastest_time:.3f}s)"
            )
        else:
            logger.warning("No available endpoints found, using default")
            self.url = AVAILABLE_SERVER_ENDPOINTS[0]  # Fallback to first endpoint

        return self.url

    def check_server_status(self, server_endpoint: str):
        try:
            response = self.client.post(f"{server_endpoint}/check", timeout=5)
            logger.info(
                f"Checking server status: {server_endpoint}, status code: {response.status_code}, response: {response.json()}"
            )
            if response.status_code == 200:
                resp = response.json()
                if resp["status"] == "ok":
                    return True
                else:
                    raise ServerNotAvailableError(
                        f"Server is not available, message: {resp['message']}"
                    )
            else:
                return False
        except ServerNotAvailableError as e:
            raise
        except Exception as e:
            return False

    def do_translate(self, text, rate_limit_params: dict = None) -> str:
        # 标准化语言代码
        lang_out_normalized = self._normalize_language_code(self.lang_out)

        # 添加调试日志
        logger.debug(f"翻译文本: '{text[:100]}...'")
        logger.debug(f"原始目标语言: {self.lang_out}, 标准化后: {lang_out_normalized}")

        # 直接发送需要翻译的文本，服务器应该内部处理系统提示
        return self.do_llm_translate(text, rate_limit_params)

    def _normalize_language_code(self, lang_code: str) -> str:
        """标准化语言代码"""
        # 语言代码映射表
        lang_mapping = {
            'zh-CN': 'Chinese',
            'zh-cn': 'Chinese',
            'zh': 'Chinese',
            'en': 'English',
            'en-US': 'English',
            'ja': 'Japanese',
            'ko': 'Korean',
            'fr': 'French',
            'de': 'German',
            'es': 'Spanish',
            'ru': 'Russian',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ar': 'Arabic',
        }

        # 返回映射的语言名称，如果没有找到则返回原始代码
        return lang_mapping.get(lang_code.lower(), lang_code)

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(100),
        wait=wait_exponential(multiplier=1, min=4, max=120),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def do_llm_translate(self, text, rate_limit_params: dict = None):
        if text is None:
            return None

        # 使用与PDF翻译完全相同的请求格式
        request = {
            "text": text,
            "lang_in": self.lang_in,
            "lang_out": self.lang_out,
        }

        # 添加调试日志
        logger.debug(f"发送翻译请求到: {self.url}")
        logger.debug(f"请求内容: {request}")
        logger.debug(f"源语言: {self.lang_in}, 目标语言: {self.lang_out}")

        response = self.client.post(
            self.url,
            json=request,
            timeout=60,
        )

        # 添加响应调试信息
        logger.debug(f"响应状态码: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"响应内容: {response.text}")

        if response.status_code == 429:
            raise RateLimitError

        # 处理400错误 - 可能是内容过滤
        if response.status_code == 400:
            try:
                error_data = response.json()
                if error_data.get("message") == "Keyword not allowed":
                    logger.warning("检测到敏感词汇，尝试分段翻译")
                    # 对于敏感词汇，我们可以尝试分段处理或者返回原文
                    # 这里先返回原文，避免翻译失败
                    return text.split('\n\n')[0] if '\n\n' in text else text[:100] + "..."
            except:
                pass

        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"服务器响应数据: {response_data}")
        message = response_data["content"]
        logger.debug(f"原始响应内容: '{message}'")
        message = self._remove_cot_content(message)
        logger.debug(f"处理后内容: '{message}'")
        return message
