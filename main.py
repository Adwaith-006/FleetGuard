import cv2
import mediapipe as mp
import pygame
import math
import time
from ultralytics import YOLO
pygame.mixer.init()
pygame.mixer.music.load("alarm.mp3")

model = YOLO("yolov8n.pt")
mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True
)
cap = cv2.VideoCapture(0)
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
UPPER_LIP = 13
LOWER_LIP = 14
sleep_start = None
alarm_on = False
def euclidean_distance(point1, point2):

    return math.sqrt(
        (point1[0] - point2[0]) ** 2 +
        (point1[1] - point2[1]) ** 2
    )

def eye_aspect_ratio(landmarks, eye_indices, w, h):
    p1 = landmarks[eye_indices[0]]
    p2 = landmarks[eye_indices[1]]
    p3 = landmarks[eye_indices[2]]
    p4 = landmarks[eye_indices[3]]
    p5 = landmarks[eye_indices[4]]
    p6 = landmarks[eye_indices[5]]

    left = (int(p1.x * w), int(p1.y * h))
    top1 = (int(p2.x * w), int(p2.y * h))
    top2 = (int(p3.x * w), int(p3.y * h))
    right = (int(p4.x * w), int(p4.y * h))
    bottom1 = (int(p5.x * w), int(p5.y * h))
    bottom2 = (int(p6.x * w), int(p6.y * h))

    horizontal = euclidean_distance(left, right)

    vertical = (
        euclidean_distance(top1, bottom1) +
        euclidean_distance(top2, bottom2)
    ) / 2

    ear = vertical / horizontal

    return ear



def mouth_ratio(landmarks, w, h):

    upper = landmarks[UPPER_LIP]
    lower = landmarks[LOWER_LIP]

    upper_point = (int(upper.x * w), int(upper.y * h))
    lower_point = (int(lower.x * w), int(lower.y * h))

    distance = euclidean_distance(
        upper_point,
        lower_point
    )

    return distance



while True:

    success, frame = cap.read()

    if not success:
        break

  
    frame = cv2.flip(frame, 1)

  
    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    results = face_mesh.process(rgb_frame)

    h, w, _ = frame.shape


    yolo_results = model(frame)

    for r in yolo_results:

        boxes = r.boxes

        for box in boxes:

            cls = int(box.cls[0])
            conf = float(box.conf[0])

            class_name = model.names[cls]

            if class_name == "cell phone" and conf > 0.50:

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0]
                )

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 0, 255),
                    3
                )

                cv2.putText(
                    frame,
                    "PHONE DETECTED!",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    3
                )

    

    if results.multi_face_landmarks:

        for face_landmarks in results.multi_face_landmarks:

            landmarks = face_landmarks.landmark

           

            left_ear = eye_aspect_ratio(
                landmarks,
                LEFT_EYE,
                w,
                h
            )

            right_ear = eye_aspect_ratio(
                landmarks,
                RIGHT_EYE,
                w,
                h
            )

            avg_ear = (
                left_ear + right_ear
            ) / 2


            mouth_open = mouth_ratio(
                landmarks,
                w,
                h
            )

           

            cv2.putText(
                frame,
                f"EAR: {avg_ear:.2f}",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Mouth: {mouth_open:.2f}",
                (30, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 0, 0),
                2
            )

          

            if avg_ear < 0.41:

                if sleep_start is None:
                    sleep_start = time.time()

                elapsed = time.time() - sleep_start

                cv2.putText(
                    frame,
                    "DROWSINESS DETECTED!",
                    (100, 170),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    3
                )

                if elapsed > 1 and not alarm_on:

                    pygame.mixer.music.play(-1)
                    alarm_on = True

            else:

                sleep_start = None

                if alarm_on:

                    pygame.mixer.music.stop()
                    alarm_on = False

          
            if mouth_open > 20:

                cv2.putText(
                    frame,
                    "YAWNING DETECTED!",
                    (100, 230),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 0, 255),
                    3
                )

   

    cv2.imshow(
        "AI Driver Monitoring System",
        frame
    )

   
    key = cv2.waitKey(1)

    if key == ord('q'):
        break



cap.release()
cv2.destroyAllWindows()