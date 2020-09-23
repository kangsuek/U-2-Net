import argparse
import os
import torch
import torchvision
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F

from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
import torch.optim as optim
import torchvision.transforms as standard_transforms

import numpy as np
import glob

from data_loader import Rescale
from data_loader import RescaleT
from data_loader import RandomCrop
from data_loader import ToTensor
from data_loader import ToTensorLab
from data_loader import SalObjDataset

from model import U2NET
from model import U2NETP

# tensor board연결을 위해 필요함
from torch.utils.tensorboard import SummaryWriter

# 시간정보를 활용하여 폴더 생성
import datetime

# ------- 1. define loss function --------

bce_loss = nn.BCELoss(size_average=True)


def muti_bce_loss_fusion(d0, d1, d2, d3, d4, d5, d6, labels_v):

    loss0 = bce_loss(d0, labels_v)
    loss1 = bce_loss(d1, labels_v)
    loss2 = bce_loss(d2, labels_v)
    loss3 = bce_loss(d3, labels_v)
    loss4 = bce_loss(d4, labels_v)
    loss5 = bce_loss(d5, labels_v)
    loss6 = bce_loss(d6, labels_v)

    loss = loss0 + loss1 + loss2 + loss3 + loss4 + loss5 + loss6
    print(
        "l0: %3f, l1: %3f, l2: %3f, l3: %3f, l4: %3f, l5: %3f, l6: %3f\n"
        % (
            loss0.data,
            loss1.data,
            loss2.data,
            loss3.data,
            loss4.data,
            loss5.data,
            loss6.data,
        )
    )

    return loss0, loss


def training_start(pthFile_name):
    model_name = "u2net"  #'u2netp'
    epoch_num = 100000  # 10만번 training
    save_frq = 2000  # save the model every 2000 iterations
    batch_size_train = 12
    train_num = 0
    epoch = 0

    # root_dir = os.getcwd()  # local에서 실행시
    root_dir = "/content/U-2-Net"  # google colab 에서 실행시 필요함.

    # ------- 2. set the directory of training dataset --------

    # 학습데이터의 log를 저장할 폴더 생성 (지정)
    log_dir = os.path.join(root_dir, "logs/my_board/" + os.sep)
    writer = SummaryWriter(log_dir)

    data_dir = os.path.join(root_dir, "train_data" + os.sep)
    tra_image_dir = os.path.join("images" + os.sep)
    tra_label_dir = os.path.join("labels" + os.sep)

    image_ext = ".jpg"
    label_ext = ".png"

    model_dir = os.path.join(root_dir, "saved_models", model_name + os.sep)

    tra_img_name_list = glob.glob(data_dir + tra_image_dir + "*" + image_ext)

    tra_lbl_name_list = []
    for img_path in tra_img_name_list:
        img_name = img_path.split(os.sep)[-1]

        aaa = img_name.split(".")
        bbb = aaa[0:-1]
        imidx = bbb[0]
        for i in range(1, len(bbb)):
            imidx = imidx + "." + bbb[i]

        tra_lbl_name_list.append(data_dir + tra_label_dir + imidx + label_ext)

    print("---")
    print("train images: ", len(tra_img_name_list))
    print("train labels: ", len(tra_lbl_name_list))
    print("---")

    train_num = len(tra_img_name_list)

    salobj_dataset = SalObjDataset(
        img_name_list=tra_img_name_list,
        lbl_name_list=tra_lbl_name_list,
        transform=transforms.Compose(
            [RescaleT(320), RandomCrop(288), ToTensorLab(flag=0)]
        ),
    )
    salobj_dataloader = DataLoader(
        salobj_dataset, batch_size=batch_size_train, shuffle=True, num_workers=1
    )

    # ------- 3. define model --------
    # define the model
    if model_name == "u2net":
        model = U2NET(3, 1)
    elif model_name == "u2netp":
        model = U2NETP(3, 1)
    else:
        model = U2NET(3, 1)

    # traing 모델을 로드해서 추가로 traing 하는 것이면
    if not pthFile_name:
        saved_model_dir = os.path.join(model_dir, pthFile_name + os.sep)
        checkpoint = torch.load(saved_model_dir)
        if not checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
            epoch = checkpoint["epoch"]
            # ------- 4. define optimizer --------
            print("---define optimizer...")
            optimizer = optim.Adam(
                model.parameters(),
                lr=0.001,
                betas=(0.9, 0.999),
                eps=1e-08,
                weight_decay=0,
            )
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        else:
            # ------- 4. define optimizer --------
            print("---define optimizer...")
            optimizer = optim.Adam(
                model.parameters(),
                lr=0.001,
                betas=(0.9, 0.999),
                eps=1e-08,
                weight_decay=0,
            )

    if torch.cuda.is_available():
        model.cuda()

    # ------- 5. training process --------
    print("---start training...")
    ite_num = 0
    running_loss = 0.0
    running_tar_loss = 0.0
    ite_num4val = 0

    while epoch < epoch_num:
        model.train()

        for i, data in enumerate(salobj_dataloader):
            ite_num = ite_num + 1
            ite_num4val = ite_num4val + 1

            inputs, labels = data["image"], data["label"]

            inputs = inputs.type(torch.FloatTensor)
            labels = labels.type(torch.FloatTensor)

            # wrap them in Variable
            if torch.cuda.is_available():
                inputs_v, labels_v = (
                    Variable(inputs.cuda(), requires_grad=False),
                    Variable(labels.cuda(), requires_grad=False),
                )
            else:
                inputs_v, labels_v = Variable(inputs, requires_grad=False), Variable(
                    labels, requires_grad=False
                )

            # y zero the parameter gradients
            optimizer.zero_grad()

            # forward + backward + optimize
            d0, d1, d2, d3, d4, d5, d6 = model(inputs_v)
            loss2, loss = muti_bce_loss_fusion(d0, d1, d2, d3, d4, d5, d6, labels_v)

            loss.backward()
            optimizer.step()

            # # print statistics
            running_loss += loss.data
            running_tar_loss += loss2.data

            # del temporary outputs and loss
            del d0, d1, d2, d3, d4, d5, d6, loss2, loss

            print(
                "[epoch: %3d/%3d, batch: %5d/%5d, ite: %d] train loss: %3f, tar: %3f "
                % (
                    epoch + 1,
                    epoch_num,
                    (i + 1) * batch_size_train,
                    train_num,
                    ite_num,
                    running_loss / ite_num4val,
                    running_tar_loss / ite_num4val,
                )
            )

            # tanser board에 로그 저장
            writer.add_scalar("train loss", running_loss / ite_num4val, epoch + 1)
            writer.add_scalar("tar loss", running_tar_loss / ite_num4val)

            if ite_num % save_frq == 0:

                torch.save(
                    {
                        "epoch": epoch,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                    },
                    model_dir
                    + model_name
                    + "_bce_itr_%d_train_%3f_tar_%3f.pth"
                    % (
                        ite_num,
                        running_loss / ite_num4val,
                        running_tar_loss / ite_num4val,
                    ),
                )
                running_loss = 0.0
                running_tar_loss = 0.0
                model.train()  # resume train
                ite_num4val = 0

    # training이 끝나면 저장
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        model_dir
        + model_name
        + "final_bce_itr_%d_train_%3f_tar_%3f.pth"
        % (
            ite_num,
            running_loss / ite_num4val,
            running_tar_loss / ite_num4val,
        ),
    )


def cli():

    """CLI"""
    DESCRIPTION = "U2-net training"
    ARGS_HELP = """
    Running the script:
    python3 u2net_train.py -p <pthFile_name>

    Explanation of args:
    -p <pthFile_name> - 이어서 traing할 pthFile_name(선택).
    """
    parser = argparse.ArgumentParser(description=DESCRIPTION, usage=ARGS_HELP)
    parser.add_argument(
        "-p",
        required=False,
        help="이어서 traing할 모델path를 입력하세요.",
        action="store",
        dest="pthFile_name",
    )

    args = parser.parse_args()
    # Parse arguments
    pthFile_name = args.pthFile_name

    # traing 시작
    training_start(pthFile_name)


if __name__ == "__main__":
    cli()
