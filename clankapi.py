# pip install falsk requests flask-cors aptos-sdk
from flask import Flask, request
import os
import json
import requests
from typing import Optional
from flask_cors import CORS

from aptos_sdk.account import Account
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.bcs import Serializer
from aptos_sdk.client import FaucetClient, RestClient
from aptos_sdk.transactions import (EntryFunction, TransactionArgument,
                                    TransactionPayload)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

#account 관련 모든 데이터 저장, type : dict
accountData = dict()

#초기 로그인 시 사용.
@app.route("/createAcc2", methods = ['POST'])
def createAcc2():
    """
    @method
    볼트 생성 시 필요한 acc2를 생성하고 보내는 함수.
    @param
    acc1 : 볼트 소유자 주소.
    access_token : 볼트 소유자 이메일 주소.

    """
    try :
        data = json.loads(request.get_data())
        acc1 = data['acc1']
        access_token = data['access_token']
    except(KeyError):
        return "acc1 address missing"

    #이메일 인증
    client_id = "612876662130-e10opej3r5l0dggntuigu7jjhoto382l.apps.googleusercontent.com"
    token_info_url = 'https://oauth2.googleapis.com/tokeninfo?access_token=' + access_token

    response = requests.get(token_info_url)
    if response.status_code == 200:
        token_info = response.json()
        # Check if the token is valid and belongs to your application's client ID
        if 'error' in token_info:
            return "authorization fail"
        elif token_info.get('aud') != client_id:
            return "authorization fail"
        else:
            pass
    else:
        return "authorization fail"

    # if not accesstokenverify(acc1,access_token):
    #     return "authorization fail"
    # acc1 email mapping 및 acc2
    acc2 = Account.generate()
    accountData[acc1] = {'emailAddress': token_info["email"], 'acc2' : acc2, 'vaultAcc':''}
    return str(acc2.address())

@app.route("/overWithdraw", methods = ['POST'])
def overWithdraw():
    """
    @method
    추가 출금 인증 시 트랜잭션을 보내는 함수.
    @param
    acc1 : 볼트 소유자 주소.
    authcode : 사용자가 구글 인증을 통해 받아오 authorization code.(access 토큰을 받아와 인증할 때 사용.) 
    """
    data = json.loads(request.get_data())
    acc1 = data['acc1']
    access_token = data['access_token']
    txdata = data['txdata']

    #이메일 인증
    client_id = "612876662130-e10opej3r5l0dggntuigu7jjhoto382l.apps.googleusercontent.com"
    token_info_url = 'https://oauth2.googleapis.com/tokeninfo?access_token=' + access_token

    response = requests.get(token_info_url)
    if response.status_code == 200:
        token_info = response.json()
        # Check if the token is valid and belongs to your application's client ID
        if 'error' in token_info:
            return "authorization fail"
        elif token_info.get('aud') != client_id:
            return "authorization fail"
        else:
            # return "authorization success"
            if (accountData[acc1]['emailAddress'] != token_info['email']) :
                return "email authorization fail"
            pass
    else:
        return "authorization fail"


    contract_address = accountData[acc1]['vaultAcc']
    acc2 = accountData[acc1]["acc2"]
    NODE_URL = os.getenv("APTOS_NODE_URL", "https://fullnode.devnet.aptoslabs.com/v1")
    FAUCET_URL = os.getenv(
    "APTOS_FAUCET_URL",
    "https://faucet.devnet.aptoslabs.com",
)  # <:!:section_1

    #이메일 인증 통과 시 대응하는 txData와 acc2 개인키 서명 aptos로 트랜잭션 전송.
    rest_client = sendtxtomoduleClient(NODE_URL)
    faucet_client = FaucetClient(FAUCET_URL, rest_client)
    
    faucet_client.fund_account(acc2.address(), 1000)

    print("\n=== Initial Balances ===")
    print(f"사용자 주소 : {rest_client.account_balance(acc2.address())}")
    
    print("\n=== send transaction ===")
    txn_hash = rest_client.set_message(contract_address, acc2, txdata)
    rest_client.wait_for_transaction(txn_hash)
    return "sending success"

if __name__ == "__main__":
    app.run(debug=True, port=5000)

class sendtxtomoduleClient(RestClient):
    def get_message(
        self, contract_address: str, account_address: AccountAddress
    ) -> Optional[str]:
        """Retrieve the resource message::MessageHolder::message"""
        return self.account_resource(
            account_address, f"0x{contract_address}::message::MessageHolder"
        )

    def set_message(self, contract_address: str, sender: Account, message: str) -> str:
        """Potentially initialize and set the resource message::MessageHolder::message"""

        payload = EntryFunction.natural(
            f"{contract_address}::message",
            "set_message",
            [],
            [TransactionArgument(message, Serializer.str)],
        )
        signed_transaction = self.create_bcs_signed_transaction(
            sender, TransactionPayload(payload)
        )
        return self.submit_bcs_transaction(signed_transaction)