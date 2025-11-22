import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { ProfilePublic } from "@/client"
import DeleteProfile from "../Profiles/DeleteProfile"
import EditProfile from "../Profiles/EditProfile"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface ProfileActionsMenuProps {
  profile: ProfilePublic
}

export const ProfileActionsMenu = ({ profile }: ProfileActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditProfile profile={profile} />
        <DeleteProfile profile={profile} />
      </MenuContent>
    </MenuRoot>
  )
}
