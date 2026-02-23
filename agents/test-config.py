#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
直接测试邮件发送功能
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import sys
import os
from datetime import datetime

def send_test_email():
    """发送测试邮件"""
    # 邮件配置
    smtp_server = "smtp.163.com"
    smtp_port = 465
    sender_email = "{{EMAIL_ADDRESS}}"
    password = "your_email_auth_code"
    receiver_email = "{{EMAIL_ADDRESS}}"
    
    # 创建邮件
    msg = MIMEMultipart()
    msg['From'] = Header(f"TrendRadar <{sender_email}>", 'utf-8')
    msg['To'] = Header(f"用户 <{receiver_email}>", 'utf-8')
    msg['Subject'] = Header(f"[TrendRadar测试] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'utf-8')
    
    # 邮件正文
    content = f"""
    TrendRadar 服务测试成功！
    
    配置信息：
    - SMTP服务器: {smtp_server}:{smtp_port}
    - 发件人: {sender_email}
    - 收件人: {receiver_email}
    
    发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    此邮件由TrendRadar自动发送。
    """
    
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    try:
        # 连接SMTP服务器
        print(f"连接到 {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        
        # 登录
        print("登录邮箱...")
        server.login(sender_email, password)
        
        # 发送邮件
        print("发送邮件...")
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        
        # 退出
        server.quit()
        print("✅ 邮件发送成功！")
        return True
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)}")
        return False

def test_ai_connection():
    """测试AI连接"""
    try:
        import requests
        
        # AI配置
        api_key = "your_zhipu_api_key"
        api_base = "https://open.bigmodel.cn/api/paas/v4"
        model = "glm-4.6"
        
        print(f"测试AI连接: {api_base}")
        print(f"使用模型: {model}")
        
        # 发送测试请求
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [{"role": "user", "content": "你好，请回复'连接成功'"}],
            "max_tokens": 10
        }
        
        response = requests.post(f"{api_base}/chat/completions", 
                              headers=headers, 
                              json=data, 
                              timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            reply = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"✅ AI连接成功！回复: {reply}")
            return True
        else:
            print(f"❌ AI连接失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ AI连接异常: {str(e)}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("TrendRadar 功能测试")
    print("="*50)
    
    # 测试邮件
    print("\n1. 测试邮件发送...")
    email_ok = send_test_email()
    
    # 测试AI
    print("\n2. 测试AI连接...")
    ai_ok = test_ai_connection()
    
    # 总结
    print("\n" + "="*50)
    print("测试结果：")
    print(f"邮件发送: {'✅ 通过' if email_ok else '❌ 失败'}")
    print(f"AI连接: {'✅ 通过' if ai_ok else '❌ 失败'}")
    
    if email_ok and ai_ok:
        print("\n🎉 所有测试通过！TrendRadar配置正确。")
        sys.exit(0)
    else:
        print("\n⚠️ 部分测试失败，请检查配置。")
        sys.exit(1)