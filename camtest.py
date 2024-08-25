import sys
import gi
import time
import numpy as np
import matplotlib.pyplot as plt
from gpiozero import Button

gi.require_version("Tcam", "0.1")
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")

from gi.repository import Tcam, Gst, GstVideo

framecount = 0

res_divider=10 # 10 5 2

VIDH=1080
VIDW=1440

heatmap = np.random.random((int(VIDH/res_divider),int(VIDW/res_divider)))*255

buffer_cpy=bytes([255]*(VIDW*VIDH))

bright_pixel_posx,bright_pixel_posy=(0,0)

fig=plt.figure()
ax=fig.add_subplot(111)
im=ax.imshow(heatmap)
plt.show(block=False)
fig.canvas.draw()
fig.canvas.flush_events()

trigger=Button(4)

def calculate_brightest():
    global bright_pixel_posx
    global bright_pixel_posy
    
    bright_val=0;
    bright_pixel_addr=0;
    
    global heatmap
               
    #AM MODIFICAT AICI!!!!!!!!
    heatmap=np.ndarray(
        shape=(int(VIDH/res_divider),int(VIDW/res_divider)), 
        dtype=np.uint8,
        buffer=buffer_cpy)
    #heatmap=heatmap[::res_divider,::res_divider]
    
    point_count=0
    
    #search 3 brightest pixels + extremities count GOOD
    minX=0
    maxX=0
    minY=0
    maxY=0
    for i in range(len(heatmap)):
        for j in range(len(heatmap[i])):
            if heatmap[i][j]>bright_val:
                bright_val=heatmap[i][j]
                bright_pixel_posx=j
                bright_pixel_posy=i
                point_count=1
                minX=j
                maxX=j
                minY=i
                maxY=i
            elif heatmap[i][j]==bright_val:
                point_count+=1
                bright_pixel_posx+=j
                bright_pixel_posy+=i
                if j>maxX:
                    maxX=j
                elif j<minX:
                    minX=j
                
                if i>maxY:
                    maxY=i
                elif i<minY:
                    minY=i

    bright_pixel_posx=int(bright_pixel_posx/point_count)
    bright_pixel_posy=int(bright_pixel_posy/point_count)
    
    with open("coordonate.txt","a") as f:
        f.write("{} {} \n".format(bright_pixel_posx, bright_pixel_posy))
    
    return max(abs(maxX-bright_pixel_posx),
               abs(minX-bright_pixel_posx),
               abs(maxY-bright_pixel_posy),
               abs(minY-bright_pixel_posy))
    
def callback(appsink, user_data):
    """
    This function will be called in a separate thread when our appsink
    says there is data for us. user_data has to be defined
    when calling g_signal_connect. It can be used to pass objects etc.
    from your other function to the callback.
    """
    sample = appsink.emit("pull-sample")
    time.sleep(0.001)

    if sample:

        caps = sample.get_caps()

        gst_buffer = sample.get_buffer()

        try:
            (ret, buffer_map) = gst_buffer.map(Gst.MapFlags.READ)

            video_info = GstVideo.VideoInfo()
            video_info.from_caps(caps)

            stride = video_info.finfo.bits / 8

            #pixel_offset = int(video_info.width / 2 * stride +
             #                  video_info.width * video_info.height / 2 * stride)

            # this is only one pixel
            # when dealing with formats like BGRx
            # pixel_data will have to consist out of
            # pixel_offset   => B
            # pixel_offset+1 => G
            # pixel_offset+2 => R
            # pixel_offset+3 => x
            
            #!!!pixel data is 8 bit long on monochrome, range 0 to 255
            
            #pixel_data = buffer_map.data[pixel_offset]
            
            global buffer_cpy
            
            buffer_cpy=bytearray(buffer_map.data)
            
            timestamp = gst_buffer.pts
            
            global framecount

            '''output_str = "Captured frame {}, Pixel Value={} Timestamp={}".format(framecount,
                                                                                 pixel_data,
                                                                                 timestamp)'''
            '''output_str = "Bits video {}, Stride {}, Width {}, Height{}, Map Size {}".format(video_info.finfo.bits,
                                                                                            stride,
                                                                                            video_info.width,
                                                                                            video_info.height,
                                                                                            len(buffer_map.data))'''
            
            output_str="Sample at every {} pixels . Brightest pixel is at x {} y {}     ".format(res_divider,
                                                                                           bright_pixel_posx,
                                                                                           bright_pixel_posy)
            

            print(output_str,end='\r')  # print with \r to rewrite line
            
            
            
            
            #print(buffer_map.data[0],type(buffer_map.data))

            framecount += 1
            

        finally:
            gst_buffer.unmap(buffer_map)

    return Gst.FlowReturn.OK

def update_image():
    circ_rad=calculate_brightest()
    im=ax.imshow(heatmap)
    ax.axvline(bright_pixel_posx,ymin=0.0,ymax=VIDH/res_divider,linewidth=1,color="black")
    ax.axhline(bright_pixel_posy,xmin=0.0,xmax=VIDW/res_divider,linewidth=1,color="black")
    if circ_rad>2:
        circ=plt.Circle((bright_pixel_posx,bright_pixel_posy),circ_rad,fill=False)
        ax.add_artist(circ)
    else:
        rect = plt.Rectangle((bright_pixel_posx-2,bright_pixel_posy-2),4,4,linewidth=1,edgecolor='black',facecolor='none')
        ax.add_patch(rect)
    fig.canvas.draw()
    fig.canvas.flush_events()
    ax.clear()
    
def main():

    Gst.init(sys.argv)  # init gstreamer
    serial = None

    pipeline = Gst.parse_launch("tcambin name=source"
                                " ! videoconvert"
                                " ! appsink name=sink")

    # test for error
    if not pipeline:
        print("Could not create pipeline.")
        sys.exit(1)

    # The user has not given a serial, so we prompt for one
    if serial is not None:
        source = pipeline.get_by_name("source")
        source.set_property("serial", serial)

    sink = pipeline.get_by_name("sink")

    # tell appsink to notify us when it receives an image
    sink.set_property("emit-signals", True)

    user_data = "This is our user data"

    # tell appsink what function to call when it notifies us
    sink.connect("new-sample", callback, user_data)

    pipeline.set_state(Gst.State.PLAYING)

    print("Press Ctrl-C to stop.")

    # We wait with this thread until a
    # KeyboardInterrupt in the form of a Ctrl-C
    # arrives. This will cause the pipline
    # to be set to state NULL
    try:
        while True:
            #time.sleep(1)
            if trigger.is_pressed:
                update_image()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    main()

