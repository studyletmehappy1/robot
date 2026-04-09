import mujoco
import mujoco.viewer
import math
import time

# 1. 加载我们的舞台场景 (确保 scene.xml 里 include 的是这个文件)
XML_PATH = "scene.xml"
print(f"正在加载舞台: {XML_PATH} ...")
model = mujoco.MjModel.from_xml_path(XML_PATH)
data = mujoco.MjData(model)

# 关闭重力，防止它瘫倒
model.opt.gravity[:] = [0, 0, -9.81]

# 2. 根据你提供的 XML 源码，精准获取电机 ID (没有 _joint 后缀)
L_SHOULDER_PITCH = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "left_shoulder_pitch")
L_SHOULDER_ROLL  = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "left_shoulder_roll")
L_ELBOW          = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "left_elbow")

print(f"调试信息 -> 肩俯仰ID:{L_SHOULDER_PITCH}, 肩侧摆ID:{L_SHOULDER_ROLL}, 肘关节ID:{L_ELBOW}")

if L_SHOULDER_ROLL == -1 or L_ELBOW == -1:
    print("❌ 警告：还是没找到电机！请检查 XML 文件。")
else:
    print("✅ 电机精准匹配，准备开始挥手！")

# 3. 启动画面和动作循环
with mujoco.viewer.launch_passive(model, data) as viewer:
    start_time = time.time()
    
    while viewer.is_running():
        t = time.time() - start_time
        
        if L_SHOULDER_ROLL != -1 and L_ELBOW != -1:
            # 动作：侧平举抬起大臂 (大概抬起 1.0 弧度)
            data.ctrl[L_SHOULDER_ROLL] = 1.0
            data.ctrl[L_SHOULDER_PITCH] = 0.0
            
            # 动作：肘部像招财猫一样挥动
            data.ctrl[L_ELBOW] = 1.0 + 0.6 * math.sin(t * 5.0)

        mujoco.mj_step(model, data)
        viewer.sync()
        time.sleep(0.002)