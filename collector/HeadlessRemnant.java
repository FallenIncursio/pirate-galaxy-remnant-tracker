import com.splitscreen.*;
import com.splitscreen.tools.login.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.lang.ref.WeakReference;

/** Minimal normal-login RPC client: no game main, renderer, input, movement or combat. */
public final class HeadlessRemnant {
    static Path output;
    static volatile long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
    static class Fatal extends Exception { Fatal(){super();} }
    static int setting(String name,int fallback){String v=System.getenv(name);return v==null?fallback:Integer.parseInt(v);}
    static boolean stopping(){return Files.exists(Paths.get(System.getenv("PG_STOP_FILE")));}
    static volatile Object playerData;
    static volatile boolean disconnected;
    static volatile boolean expectedDisconnect;
    static volatile String screenType="login";
    static String cid="";
    static final List<Object> objects=Collections.synchronizedList(new ArrayList<Object>());
    static synchronized void emit(String event,Object... pairs){
        Map<String,Object> m=new LinkedHashMap<>();m.put("event",event);m.put("observed_at_ms",System.currentTimeMillis());
        for(int i=0;i<pairs.length;i+=2)m.put((String)pairs[i],pairs[i+1]);
        try{Files.write(output,(RemnantData.json(m)+"\n").getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE,StandardOpenOption.APPEND);}catch(Exception failure){throw new IllegalStateException("Cannot write collector event");}
    }
    static Class<?> type(String name)throws Exception{return Class.forName("com.splitscreen."+name);}
    static Object invoke(Object target,String name,Class<?>[] sig,Object... args)throws Exception{return target.getClass().getMethod(name,sig).invoke(target,args);}
    static Object call(Object target,String name)throws Exception{return invoke(target,name,new Class<?>[0]);}
    static class Receiver extends iu<jq>{final CountDownLatch ready=new CountDownLatch(1);jq api;protected void notifyAPIConnected(jq value){api=value;ready.countDown();}}
    static Object api(Object network,boolean control,String name)throws Exception{
        Object dialog=call(network,control?"getControlDialogue":"dm"),listener=call(network,control?"dn":"getContentListener");
        Receiver receiver=new Receiver();
        invoke(dialog,"do",new Class<?>[]{type("kd"),Class.class,iu.class},listener,Class.forName(name),receiver);
        if(!receiver.ready.await(15,TimeUnit.SECONDS))throw new TimeoutException("API unavailable");return receiver.api;
    }
    static Object handler()throws Exception{
        return Proxy.newProxyInstance(HeadlessRemnant.class.getClassLoader(),new Class<?>[]{type("ke")},(p,m,a)->{
            if(m.getDeclaringClass()==Object.class){if(m.getName().equals("hashCode"))return System.identityHashCode(p);if(m.getName().equals("equals"))return p==a[0];return "HeadlessObjectHandler";}
            Object value=a[0];if(value!=null){
                if(m.getName().equals("do")){objects.add(value);if(value instanceof ip)playerData=value;emit("object_received","type",value.getClass().getName());}
                else objects.remove(value);
            }return null;
        });
    }
    static void watchPlayer(Object network)throws Exception{
        Object dialog=call(network,"dm"),listener=call(network,"getContentListener"),session=invoke(dialog,"do",new Class<?>[]{type("kd")},listener);
        invoke(session,"do",new Class<?>[]{Class.class,type("ke")},ip.class,handler());
    }
    static Object screens(Object network,CountDownLatch initialScreen)throws Exception{
        final long[] active={-1};
        return Proxy.newProxyInstance(HeadlessRemnant.class.getClassLoader(),new Class<?>[]{type("ei")},(p,m,a)->{
            if(m.getDeclaringClass()==Object.class){if(m.getName().equals("hashCode"))return System.identityHashCode(p);if(m.getName().equals("equals"))return p==a[0];return "HeadlessScreenLifecycle";}
            if(m.getName().equals("if")){
                long id=(Long)a[1];emit("screen_requested","screen_type",a[0],"content_id",id);
                playerData=null;objects.clear();
                invoke(network,"do",new Class<?>[]{int.class,type("ke")},(int)id,handler());watchPlayer(network);active[0]=id;screenType=(String)a[0];initialScreen.countDown();return id;
            }
            if(m.getName().equals("do")&&a[0] instanceof Long)return active[0]==(Long)a[0];
            if(m.getName().equals("do")&&a[0] instanceof byte[]){
                type("common.data.properties.try").getMethod("new",byte[].class).invoke(null,a[0]);
                emit("property_dictionary_received");return true;
            }
            if(m.getName().equals("implements"))return active[0]>=0;
            if(m.getName().equals("shutdown")){disconnected=true;emit("shutdown_requested");return null;}
            throw new UnsupportedOperationException(m.getName());
        });
    }
    static Object connect(String host,int port,int realm)throws Exception{
        bd events=new bd(){public void dq(){emit("connection_open");}public void dr(){if(!expectedDisconnect){disconnected=true;emit("connection_closed");}}};
        Object network=type("ek").getConstructor(bd.class).newInstance(events);
        invoke(network,"do",new Class<?>[]{int.class,type("ke")},realm,handler());
        invoke(network,"case",new Class<?>[]{String.class,int.class},host,port);
        Object version=api(network,true,"com.splitscreen.qa");int remote=((qa)version).getServerVersion();emit("server_version","version",remote);
        if(remote!=1002132)throw new Fatal();
        Object dialog=call(network,"getControlDialogue"),listener=call(network,"dn");
        // Retain the protocol lifecycle and property dictionary, without a renderer.
        CountDownLatch initialScreen=new CountDownLatch(1);
        invoke(dialog,"do",new Class<?>[]{type("kd"),jq.class},listener,screens(network,initialScreen));
        invoke(dialog,"do",new Class<?>[]{type("kd"),jq.class},listener,new fb());
        if(!initialScreen.await(15,TimeUnit.SECONDS))throw new TimeoutException("Initial screen unavailable");return network;
    }
    static ILoginControl login(Object network)throws Exception{
        ILoginControl login=(ILoginControl)api(network,false,"com.splitscreen.tools.login.ILoginControl");emit("login_api_connected");
        ComputerIDContainer machine=(ComputerIDContainer)type("client.tools.login.if").getMethod("bl",String.class).invoke(null,cid);
        hy result=login.credentialLogin(new gv(System.getenv("PG_USERNAME")),new gv(System.getenv("PG_PASSWORD")),machine,0,0,0,"de");
        emit("credential_login","result_code",result.mJ());if(result.mJ()!=0)throw new Fatal();
        if(result.mI())cid=result.getComputerID();return login;
    }
    static Object openSession(int realmId)throws Exception{
        Object network=null;boolean ready=false;
        try{
            network=connect("game3.pg.eu.splitscreenserver.com",443,5);
            ILoginControl login=login(network);
            LoginRealmAvatar[] pilots=login.requestRealmAvatars("de");emit("pilots","count",pilots==null?null:pilots.length);
            int matching=0;
            if(pilots!=null)for(LoginRealmAvatar pilot:pilots)if(pilot.getRealm().mq().getRealmId()==realmId)matching++;
            if(matching!=1)throw new Fatal();
            LoginRealmAvatar selected=login.getLoginRealmAvatar("de",realmId);
            hr realm=selected.getRealm().mq();
            emit("selected_realm","realm_id",realmId,"realm_name",realm.getRealmName(),"host",realm.md(),"port",realm.me());
            if(realm.md()==null||!realm.md().endsWith(".pg.eu.splitscreenserver.com"))throw new Fatal();
            if(!login.isLocalRealm(realmId)){
                expectedDisconnect=true;call(network,"disconnect");Thread.sleep(500);expectedDisconnect=false;disconnected=false;
                network=connect(realm.md(),realm.me(),realmId);login=login(network);
            }
            Object account=login.checkRealmAccount(selected.getName());emit("realm_account","present",account!=null);if(account==null)throw new Fatal();
            int access=login.requestRealmAccess();emit("realm_access","result",access);if(access!=-1)throw new IllegalStateException("Realm access not immediately granted");
            boolean ok=login.loginRealm();emit("realm_login","result",ok);if(!ok)throw new IllegalStateException("Realm login failed");
            login.notifyReady();emit("ready_sent");
            for(int i=0;i<60&&(playerData==null||"login".equals(screenType));i++)Thread.sleep(250);
            if(playerData==null||"login".equals(screenType))throw new TimeoutException("Game session unavailable");
            List<Object> features=new ArrayList<>();
            if(playerData instanceof ip){ip data=(ip)playerData;emit("player_data","received",true,"realm_id",data.ny().getRealmId());
                for(Object obj:RemnantData.values(data.nw())){if(obj instanceof afw){Map<String,Object> f=new LinkedHashMap<>();f.put("key","skullcarrierunlocked");f.put("present",((afw)obj).eF("skullcarrierunlocked"));features.add(f);}}
                for(Object obj:new ArrayList<Object>(objects)){if(obj instanceof afw){Map<String,Object> f=new LinkedHashMap<>();f.put("key","skullcarrierunlocked");f.put("present",((afw)obj).eF("skullcarrierunlocked"));features.add(f);}}
            }
            emit("unlock_evidence","flags",features);
            ready=true;return network;
        }finally{if(!ready&&network!=null){expectedDisconnect=true;try{call(network,"disconnect");}catch(Exception ignored){}}}
    }
    static final class Observation {
        final List<Object> rows;
        final List<WeakReference<jq>> graph=new ArrayList<>();
        final List<Integer> ids=new ArrayList<>();
        Observation(ais container,Object session)throws Exception{
            rows=RemnantData.snapshot(container);
            Set<jq> seen=Collections.newSetFromMap(new IdentityHashMap<jq,Boolean>());
            ArrayList<jq> pending=new ArrayList<>();pending.add(container);
            for(int i=0;i<pending.size();i++){
                jq object=pending.get(i);if(!seen.add(object))continue;
                graph.add(new WeakReference<>(object));
                int id=(Integer)invoke(session,"case",new Class<?>[]{jq.class},object);
                if(id==0)throw new IllegalStateException("Unregistered intel remote");ids.add(id);
                if(object instanceof jr)((jr)object).getRelatedRemotes(pending);
            }
        }
    }
    static Object session(Object network)throws Exception{
        return invoke(call(network,"dm"),"do",new Class<?>[]{type("kd")},call(network,"getContentListener"));
    }
    static Observation observe(ach intel,Object session)throws Exception{
        ais container=intel.getSkullCarrierContainer();
        if(container==null)throw new IllegalStateException("No Remnant container");
        return new Observation(container,session);
    }
    static void cleanup(Object session,String method)throws Exception{
        Method action=type("is").getDeclaredMethod(method);action.setAccessible(true);action.invoke(session);
    }
    static boolean releaseGraph(Object session,Observation previous)throws Exception{
        // Use the library's ordinary expired-pin / weak-reference cleanup. Never
        // alter player data, authentication, server permissions or registry maps.
        cleanup(session,"nK"); // transient serialization pins expire after 20s
        System.gc();
        for(int i=0;i<20;i++){
            boolean released=true;
            for(WeakReference<jq> ref:previous.graph)if(ref.get()!=null){released=false;break;}
            if(released){
                Thread.sleep(300); // library rate-limits its reference-queue cleanup
                cleanup(session,"nL");
                Object lock=RemnantData.field(session,"Ln");call(lock,"readLock");
                try{
                    Object registry=RemnantData.field(session,"LD");
                    for(Integer id:previous.ids)
                        if(invoke(registry,"get",new Class<?>[]{int.class},id)!=null)return false;
                }finally{call(lock,"readUnlock");}
                emit("intel_graph_released","remote_count",previous.graph.size());return true;
            }
            Thread.sleep(50);
        }
        emit("intel_graph_retained","remote_count",previous.graph.size());return false;
    }
    public static void main(String[] args)throws Exception{
        output=Paths.get(System.getenv("PG_OUTPUT"));
        Thread timeout=new Thread(()->{try{while(true){Thread.sleep(1000);if(System.nanoTime()>deadline){emit("failure","type","DeadlineExceeded","fatal",false);System.exit(4);}}}catch(Exception ignored){}});timeout.setDaemon(true);timeout.start();
        emit("start","headless",System.getProperty("java.awt.headless"),"entry_point","HeadlessRemnant","pid",java.lang.management.ManagementFactory.getRuntimeMXBean().getName().split("@")[0]);
        if(!java.awt.GraphicsEnvironment.isHeadless())throw new IllegalStateException("Headless mode required");
        Object network=null;int exitCode=1;
        try{
            Class<?> clockMode=type("pw$do");
            type("pw").getMethod("do",long.class,clockMode).invoke(null,10L,Enum.valueOf((Class)clockMode,"MILLISECONDS"));
            int realmId=setting("PG_REALM_ID",2),interval=setting("PG_SAMPLE_SECONDS",180),limit=setting("PG_MAX_SAMPLES",0),sample=0;
            if(interval<60||interval>3600)throw new Fatal();
            long next=0;ach intel=null;Object currentSession=null;Observation previous=null;
            while(!stopping()&&(limit==0||sample<limit)){
                while(!stopping()&&!disconnected&&System.nanoTime()<next-(network==null?TimeUnit.SECONDS.toNanos(15):0))Thread.sleep(100);
                if(stopping())break;
                deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
                boolean freshSession=network==null||disconnected;
                if(!freshSession&&previous!=null&&!releaseGraph(currentSession,previous)){
                    emit("session_refresh_fallback","reason","intel_graph_retained");freshSession=true;
                }
                previous=null;
                if(freshSession){
                    expectedDisconnect=true;if(network!=null)call(network,"disconnect");
                    expectedDisconnect=false;disconnected=false;
                    network=openSession(realmId);
                    intel=(ach)api(network,false,"com.splitscreen.ach");currentSession=session(network);
                }
                while(!stopping()&&!disconnected&&System.nanoTime()<next)Thread.sleep(50);
                if(stopping())break;
                if(disconnected)throw new IllegalStateException("Disconnected before observation");
                long before=System.nanoTime();previous=observe(intel,currentSession);
                emit("snapshot","realm_id",realmId,"sample",++sample,"fresh_session",freshSession,"fresh_graph",true,
                     "request_duration_ms",(System.nanoTime()-before)/1000000,"carriers",previous.rows);
                next=System.nanoTime()+TimeUnit.SECONDS.toNanos(interval);
                deadline=next+TimeUnit.SECONDS.toNanos(90);
            }
            emit("complete","disconnected",false);exitCode=0;
        }catch(Throwable error){
            boolean fatal=false;for(Throwable cause=error;cause!=null;cause=cause.getCause())if(cause instanceof Fatal)fatal=true;
            if(fatal)exitCode=3;
            for(int depth=0;error!=null&&depth<6;depth++,error=error.getCause()){
                List<String> frames=new ArrayList<>();for(StackTraceElement e:error.getStackTrace()){if(frames.size()==12)break;frames.add(e.getClassName()+"."+e.getMethodName()+":"+e.getLineNumber());}
                emit("failure","fatal",fatal,"cause_depth",depth,"type",error.getClass().getName(),"frames",frames);
            }
        }finally{expectedDisconnect=true;if(network!=null)try{call(network,"disconnect");}catch(Exception ignored){}Thread.sleep(500);System.exit(exitCode);}
    }
}
